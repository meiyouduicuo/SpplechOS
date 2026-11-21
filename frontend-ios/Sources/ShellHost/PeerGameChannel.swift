import Foundation
@preconcurrency import Network
import CryptoKit

struct PeerGameHello: Codable, Sendable {
    let schema: Int
    let bundleID: String
    let teamID: String
    let publicKey: Data
}

/// Ephemeral authenticated encryption. The displayed code binds both public keys to the session.
struct PeerGameCipher {
    private let key: SymmetricKey
    private let outgoing: Data
    private let incoming: Data
    private var sent: UInt64 = 0
    private var received: UInt64 = 0
    let code: String
    init(privateKey: Curve25519.KeyAgreement.PrivateKey, remote: Data) throws {
        let own = privateKey.publicKey.rawRepresentation
        guard own != remote else { throw GamePackage.Failure.invalid }
        let shared = try privateKey.sharedSecretFromKeyAgreement(with: .init(rawRepresentation: remote))
        let salt = own.lexicographicallyPrecedes(remote) ? own + remote : remote + own
        key = shared.hkdfDerivedSymmetricKey(using: SHA256.self, salt: salt,
            sharedInfo: Data("SpplechOS direct game transfer v1".utf8), outputByteCount: 32)
        outgoing = own; incoming = remote
        let proof = Data(HMAC<SHA256>.authenticationCode(for: Data("verify both screens".utf8), using: key))
        let number = proof.prefix(4).reduce(UInt32(0)) { ($0 << 8) | UInt32($1) } % 1_000_000
        code = String(format: "%06u", number)
    }
    private func tag(_ identity: Data, _ count: UInt64) -> Data {
        var data = identity
        var value = count.bigEndian
        withUnsafeBytes(of: &value) { data.append(contentsOf: $0) }
        return data
    }
    mutating func seal(_ data: Data) throws -> Data {
        guard sent < UInt64.max else { throw GamePackage.Failure.invalid }
        let box = try AES.GCM.seal(data, using: key, authenticating: tag(outgoing, sent))
        sent += 1
        return box.combined!
    }
    mutating func open(_ data: Data) throws -> Data {
        guard received < UInt64.max else { throw GamePackage.Failure.invalid }
        let result = try AES.GCM.open(.init(combined: data), using: key, authenticating: tag(incoming, received))
        received += 1
        return result
    }
}

/// One ordered sender and one ordered receiver. At most one payload chunk is awaiting acknowledgment.
final class PeerGameChannel: @unchecked Sendable {
    let connection: NWConnection
    private let queue = DispatchQueue(label: "org.spplechos.game-transfer")
    private var cipher: PeerGameCipher?
    init(_ connection: NWConnection) { self.connection = connection }
    func cancel() { connection.cancel() }
    func start() async throws {
        try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
            let ready = PeerReadyContinuation(continuation)
            connection.stateUpdateHandler = { state in
                switch state {
                case .ready: ready.finish(nil)
                case .failed(let error): ready.finish(error)
                case .cancelled: ready.finish(CancellationError())
                default: break
                }
            }
            connection.start(queue: queue)
        }
    }
    func handshake(bundleID: String, teamID: String) async throws -> String {
        let secret = Curve25519.KeyAgreement.PrivateKey()
        let hello = PeerGameHello(schema: 1, bundleID: bundleID, teamID: teamID, publicKey: secret.publicKey.rawRepresentation)
        try await sendFrame(JSONEncoder().encode(hello))
        let data = try await readFrame(limit: 4096)
        let other = try JSONDecoder().decode(PeerGameHello.self, from: data)
        guard other.schema == 1, !teamID.isEmpty, other.bundleID == bundleID, other.teamID == teamID else { throw GamePackage.Failure.identity }
        let crypto = try PeerGameCipher(privateKey: secret, remote: other.publicKey)
        cipher = crypto
        return crypto.code
    }
    func send(_ data: Data) async throws {
        guard var crypto = cipher else { throw GamePackage.Failure.invalid }
        let sealed = try crypto.seal(data)
        cipher = crypto
        try await sendFrame(sealed)
    }
    func read(limit: Int = GamePackage.maxHeader + 256) async throws -> Data {
        let data = try await readFrame(limit: limit)
        guard var crypto = cipher else { throw GamePackage.Failure.invalid }
        let result = try crypto.open(data)
        cipher = crypto
        return result
    }
    private func sendFrame(_ data: Data) async throws {
        guard data.count <= GamePackage.maxHeader + 256 else { throw GamePackage.Failure.invalid }
        var size = UInt32(data.count).bigEndian
        var packet = withUnsafeBytes(of: &size) { Data($0) }
        packet.append(data)
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            connection.send(content: packet, completion: .contentProcessed { error in
                if let error { c.resume(throwing: error) } else { c.resume() }
            })
        }
    }
    private func readFrame(limit: Int) async throws -> Data {
        let prefix = try await readExactly(4)
        let size = prefix.reduce(UInt32(0)) { ($0 << 8) | UInt32($1) }
        guard size > 0, Int(size) <= limit else { throw GamePackage.Failure.invalid }
        return try await readExactly(Int(size))
    }
    private func readExactly(_ count: Int) async throws -> Data {
        var result = Data()
        while result.count < count {
            try Task.checkCancellation()
            let remaining = count - result.count
            let next: Data = try await withTaskCancellationHandler {
                try await withCheckedThrowingContinuation { c in
                    connection.receive(minimumIncompleteLength: 1, maximumLength: remaining) { data, _, complete, error in
                    if let data, !data.isEmpty { c.resume(returning: data) }
                        else { c.resume(throwing: error ?? NWError.posix(.ECONNRESET)) }
                    }
                }
            } onCancel: { self.connection.cancel() }
            result.append(next)
        }
        return result
    }
}

private final class PeerReadyContinuation: @unchecked Sendable {
    private let lock = NSLock()
    private var continuation: CheckedContinuation<Void, Error>?
    init(_ continuation: CheckedContinuation<Void, Error>) { self.continuation = continuation }
    func finish(_ error: Error?) {
        lock.lock()
        let pending = continuation
        continuation = nil
        lock.unlock()
        if let error { pending?.resume(throwing: error) } else { pending?.resume() }
    }
}
