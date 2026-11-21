import Foundation
import CryptoKit
@preconcurrency import Network
import Testing
import ShellUI
import Darwin
@testable import ShellHost

struct PeerGameTransferTests {
    @Test func pairingEncryptionDetectsModificationReplayAndReflection() throws {
        let a = Curve25519.KeyAgreement.PrivateKey(), b = Curve25519.KeyAgreement.PrivateKey()
        var sender = try PeerGameCipher(privateKey: a, remote: b.publicKey.rawRepresentation)
        var receiver = try PeerGameCipher(privateKey: b, remote: a.publicKey.rawRepresentation)
        #expect(sender.code == receiver.code && sender.code.count == 6)
        let original = Data("a game chunk".utf8)
        let sealed = try sender.seal(original)
        #expect(sealed.range(of: original) == nil)
        var damaged = sealed; damaged[damaged.count - 1] ^= 1
        #expect(throws: (any Error).self) { try receiver.open(damaged) }
        #expect(try receiver.open(sealed) == original)
        #expect(throws: (any Error).self) { try receiver.open(sealed) }
        #expect(throws: (any Error).self) { try sender.open(sealed) }
        #expect(try sender.open(receiver.seal(original)) == original)
    }

    @Test func directSourceNeverCopiesASaveOrCreatesAnArchive() throws {
        let box = try Sandbox()
        let old = GamePackageTests()
        let id = try old.install(old.fixture, box: box)
        let root = box.appData.appendingPathComponent(id)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("save"), withIntermediateDirectories: true)
        try Data("private save".utf8).write(to: root.appendingPathComponent("save/main.dat"))
        let entry = GameCatalogue.readFramework(at: box.root.appendingPathComponent("hot/DmGame\(id).framework"))
        let source = try PeerGameSource.prepare(entry: entry, image: root.appendingPathComponent("romfs.img"), bundleID: old.bundleID, teamID: old.teamID)
        let sink = try PeerGameSink(manifest: source.manifest, dataRoot: box.root.appendingPathComponent("receive"),
            frameworksRoot: box.root.appendingPathComponent("receive-hot"), bundleID: old.bundleID,
            teamID: old.teamID, environment: HostEnvironment(chain: "b-3f9a2c"))
        for file in source.files where file.entry.path.hasPrefix("framework/") {
            let target = sink.stage.appendingPathComponent(file.entry.path)
            try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            try FileManager.default.copyItem(at: file.url, to: target)
        }
        #expect(FrameworkSignature.inspect(executable: sink.stage.appendingPathComponent("framework/DmGame" + id))?.teamID == old.teamID)
        try sink.checkFramework()
        #expect(source.files.allSatisfy { !$0.entry.path.contains("save/") })
        #expect(source.files.contains { $0.entry.path == "data/romfs.img" })
        #expect(source.files.first?.entry.path.hasPrefix("framework/") == true)
        #expect(source.files.contains { $0.entry.path == "framework/DmGame" + id })
        #expect(source.files.contains { $0.entry.path == "data/msl/b-3f9a2c/synthetic.metallib" })
        #expect(!source.files.contains { $0.url.pathExtension == "sppgame" })
        #expect(try FileManager.default.contentsOfDirectory(atPath: box.root.path).allSatisfy { !$0.hasSuffix("sppgame") })
    }

    @Test(.timeLimit(.minutes(3))) func encryptedLoopbackTransfersAndPreservesExistingSaves() async throws {
        let sourceBox = try Sandbox(), destination = try Sandbox()
        let old = GamePackageTests()
        let id = try old.install(old.fixture, box: sourceBox)
        print("[peer-test] fixture installed")
        let root = sourceBox.appData.appendingPathComponent(id)
        let payloadSize = ProcessInfo.processInfo.environment["SPPLECHOS_PEER_TEST_BYTES"].flatMap(Int.init) ?? 32 * 1024 * 1024
        let extra = root.appendingPathComponent("aoc/transfer-test.img")
        try FileManager.default.createDirectory(at: extra.deletingLastPathComponent(), withIntermediateDirectories: true)
        #expect(FileManager.default.createFile(atPath: extra.path, contents: nil))
        let sparse = try FileHandle(forWritingTo: extra)
        try sparse.truncate(atOffset: UInt64(payloadSize)); try sparse.close()
        let entry = GameCatalogue.readFramework(at: sourceBox.root.appendingPathComponent("hot/DmGame\(id).framework"))
        let source = try PeerGameSource.prepare(entry: entry, image: root.appendingPathComponent("romfs.img"), bundleID: old.bundleID, teamID: old.teamID)
        print("[peer-test] source prepared")
        let save = destination.appData.appendingPathComponent(id + "/save/main.dat")
        try FileManager.default.createDirectory(at: save.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("keep my save".utf8).write(to: save)
        let pair = try await LocalPeerPair.make()
        defer { pair.client.cancel(); pair.server.cancel(); pair.listener.cancel() }
        async let a = pair.client.handshake(bundleID: old.bundleID, teamID: old.teamID)
        async let b = pair.server.handshake(bundleID: old.bundleID, teamID: old.teamID)
        let codes = try await (a, b)
        #expect(codes.0 == codes.1)
        print("[peer-test] handshake compatible")
        let memory = TransferMemoryProbe()
        async let send: Void = PeerGameWire.send(source, over: pair.client, progress: { _ in memory.sample() })
        let received = try await pair.server.read()
        let offer = try JSONDecoder().decode(PeerGameWire.Offer.self, from: received)
        print("[peer-test] offer received")
        let sink = try PeerGameSink(manifest: offer.manifest, dataRoot: destination.appData,
            frameworksRoot: destination.root.appendingPathComponent("hot"), bundleID: old.bundleID,
            teamID: old.teamID, environment: HostEnvironment(chain: "b-3f9a2c"))
        print("[peer-test] receiver staged")
        try await pair.server.send(PeerGameWire.approve)
        let imported = try await PeerGameWire.receive(sink, over: pair.server, progress: { _ in memory.sample() })
        try await send
        #expect(imported == id)
        print("[peer-memory] bytes=\(payloadSize) baseline=\(memory.baseline) peak=\(memory.peak) growth=\(memory.growth)")
        #expect(memory.baseline > 0 && memory.growth < 192 * 1024 * 1024)
        #expect(try destination.appData.appendingPathComponent(id + "/aoc/transfer-test.img").resourceValues(forKeys: [.fileSizeKey]).fileSize == payloadSize)
        #expect(try Data(contentsOf: save) == Data("keep my save".utf8))
        #expect(GameCatalogue.scan(root: destination.root.appendingPathComponent("hot")).count == 1)
        #expect(try FileManager.default.contentsOfDirectory(atPath: destination.appData.path).allSatisfy { !$0.hasPrefix(".package-import-") })
    }

    @Test(.timeLimit(.minutes(1))) func signingTeamMismatchIsRejectedBeforeAnOffer() async throws {
        let pair = try await LocalPeerPair.make()
        defer { pair.client.cancel(); pair.server.cancel(); pair.listener.cancel() }
        var refused = false
        do {
            async let a = pair.client.handshake(bundleID: "org.spplechos.shell", teamID: "TEAM_A")
            async let b = pair.server.handshake(bundleID: "org.spplechos.shell", teamID: "TEAM_B")
            _ = try await (a, b)
        } catch { refused = true }
        #expect(refused)
    }

    @Test(.timeLimit(.minutes(1))) func interruptedTransferCleansStageAndPreservesInstalledGame() async throws {
        let sender = try Sandbox(), receiver = try Sandbox(), old = GamePackageTests()
        let id = try old.install(old.fixture, box: sender)
        _ = try old.install(old.fixture, box: receiver)
        let root = sender.appData.appendingPathComponent(id)
        try FileManager.default.createDirectory(at: root.appendingPathComponent("aoc"), withIntermediateDirectories: true)
        try Data(repeating: 7, count: PeerGameWire.chunkSize * 3).write(to: root.appendingPathComponent("aoc/extra.img"))
        let entry = GameCatalogue.readFramework(at: sender.root.appendingPathComponent("hot/DmGame\(id).framework"))
        let source = try PeerGameSource.prepare(entry: entry, image: root.appendingPathComponent("romfs.img"), bundleID: old.bundleID, teamID: old.teamID)
        let original = try Data(contentsOf: receiver.appData.appendingPathComponent(id + "/romfs.img"))
        let pair = try await LocalPeerPair.make()
        defer { pair.client.cancel(); pair.server.cancel(); pair.listener.cancel() }
        async let a = pair.client.handshake(bundleID: old.bundleID, teamID: old.teamID)
        async let b = pair.server.handshake(bundleID: old.bundleID, teamID: old.teamID)
        _ = try await (a, b)
        async let sending: Void = PeerGameWire.send(source, over: pair.client, progress: { _ in })
        let offer = try JSONDecoder().decode(PeerGameWire.Offer.self, from: await pair.server.read())
        do {
            let sink = try PeerGameSink(manifest: offer.manifest, dataRoot: receiver.appData,
                frameworksRoot: receiver.root.appendingPathComponent("hot"), bundleID: old.bundleID,
                teamID: old.teamID, environment: HostEnvironment(chain: "b-3f9a2c"))
            try await pair.server.send(PeerGameWire.approve)
            var failed = false
            let interrupted = TransferInterruptionProbe()
            do {
                _ = try await PeerGameWire.receive(sink, over: pair.server, progress: { value in
                    if value > 0.1 { interrupted.mark(); pair.server.cancel() }
                })
            } catch { failed = true }
            #expect(failed)
            #expect(interrupted.wasRequested, "The test must reach payload transfer before injecting disconnection")
        }
        pair.client.cancel(); pair.server.cancel()
        _ = try? await sending
        #expect(try Data(contentsOf: receiver.appData.appendingPathComponent(id + "/romfs.img")) == original)
        #expect(try FileManager.default.contentsOfDirectory(atPath: receiver.appData.path).allSatisfy { !$0.hasPrefix(".package-import-") })
    }

    @MainActor @Test func peerTransferBlocksOtherImportsLaunchAndSaveDeletion() async throws {
        let box = try Sandbox()
        let folder = try box.giveAppData()
        let save = folder.appendingPathComponent("save/main.dat")
        try FileManager.default.createDirectory(at: save.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("keep this save".utf8).write(to: save)
        var config = box.config()
        config.hotFrameworksRoot = box.root.appendingPathComponent("hot")
        let launcher = RecordingLauncher()
        let defaults = UserDefaults(suiteName: box.suite + "peer-settings")!
        let model = ShellHostModel(config: config, launcher: launcher, shellSettings: ShellSettingsStore(defaults: defaults))
        model.beginPeerTransfer(gameID: nil)
        #expect(model.peerTransfer != nil && !model.acceptsUSBImport)
        defer { model.peerTransfer?.stop(); model.peerTransfer = nil }
        model.clearGameSaves(Fixtures.orbit)
        model.deleteGame(Fixtures.orbit, saves: true)
        await model.playNow(Fixtures.orbit)
        #expect(launcher.launched.isEmpty)
        var refused = false
        do { _ = try await model.importGamePackageNow(GamePackageTests().fixture) }
        catch GamePackage.Failure.busy { refused = true }
        #expect(refused)
        #expect(try Data(contentsOf: save) == Data("keep this save".utf8))
    }

    @Test func sinkRejectsWrongTeamPathsAndDataBeforeFramework() throws {
        let box = try Sandbox(), old = GamePackageTests()
        let id = try old.install(old.fixture, box: box)
        let entry = GameCatalogue.readFramework(at: box.root.appendingPathComponent("hot/DmGame\(id).framework"))
        let source = try PeerGameSource.prepare(entry: entry, image: box.appData.appendingPathComponent(id + "/romfs.img"), bundleID: old.bundleID, teamID: old.teamID)
        for change in 0..<3 {
            var manifest = source.manifest
            if change == 0 { manifest.teamID = "OTHERTEAM" }
            if change == 1 { manifest.files[0].path = "data/save/main.dat" }
            if change == 2 { manifest.files.reverse() }
            #expect(throws: GamePackage.Failure.self) {
                try PeerGameSink(manifest: manifest, dataRoot: box.appData, frameworksRoot: box.root.appendingPathComponent("other"),
                    bundleID: old.bundleID, teamID: old.teamID, environment: HostEnvironment())
            }
        }
        #expect(try FileManager.default.contentsOfDirectory(atPath: box.appData.path).allSatisfy { !$0.hasPrefix(".package-import-") })
    }
}

private struct LocalPeerPair: @unchecked Sendable {
    let listener: NWListener
    let client: PeerGameChannel
    let server: PeerGameChannel
    static func make() async throws -> Self {
        let listener = try NWListener(using: .tcp, on: .any)
        let queue = DispatchQueue(label: "peer-transfer-test")
        let (incoming, accept) = AsyncStream<NWConnection>.makeStream(bufferingPolicy: .bufferingNewest(1))
        listener.newConnectionHandler = { accept.yield($0) }
        try await withCheckedThrowingContinuation { (c: CheckedContinuation<Void, Error>) in
            let ready = TestListenerReady(c)
            listener.stateUpdateHandler = { state in
                if case .ready = state { ready.complete(nil) }
                if case .failed(let error) = state { ready.complete(error) }
            }
            listener.start(queue: queue)
        }
        let port = try #require(listener.port)
        let client = PeerGameChannel(NWConnection(host: "127.0.0.1", port: port, using: .tcp))
        try await client.start()
        var iterator = incoming.makeAsyncIterator()
        let connection = try #require(await iterator.next())
        let accepted = PeerGameChannel(connection)
        try await accepted.start()
        return Self(listener: listener, client: client, server: accepted)
    }
}

private final class TestListenerReady: @unchecked Sendable {
    let lock = NSLock()
    var continuation: CheckedContinuation<Void, Error>?
    init(_ value: CheckedContinuation<Void, Error>) { continuation = value }
    func complete(_ error: Error?) {
        lock.lock(); let c = continuation; continuation = nil; lock.unlock()
        if let error { c?.resume(throwing: error) } else { c?.resume() }
    }
}

private final class TransferMemoryProbe: @unchecked Sendable {
    let baseline = TransferMemoryProbe.resident()
    private let lock = NSLock()
    private(set) var peak: UInt64 = 0
    var growth: UInt64 { peak - min(peak, baseline) }
    func sample() { let current = Self.resident(); lock.lock(); peak = max(peak, current); lock.unlock() }
    static func resident() -> UInt64 {
        var info = mach_task_basic_info()
        var count = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &count)
            }
        }
        return result == KERN_SUCCESS ? UInt64(info.resident_size) : 0
    }
}

private final class TransferInterruptionProbe: @unchecked Sendable {
    private let lock = NSLock()
    private var requested = false
    func mark() { lock.lock(); requested = true; lock.unlock() }
    var wasRequested: Bool { lock.lock(); defer { lock.unlock() }; return requested }
}
