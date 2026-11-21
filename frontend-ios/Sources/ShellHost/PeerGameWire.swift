import Foundation
import CryptoKit

/// A reliable, acknowledged chunk protocol, with no archive on either device.
enum PeerGameWire {
    static let chunkSize = 1024 * 1024
    static let approve = Data([1]), ack = Data([2]), finish = Data([3])
    struct Offer: Codable, Sendable { let title: String; let manifest: GamePackage.Manifest }

    static func send(_ source: PeerGameSource, over channel: PeerGameChannel,
                     progress: @Sendable (Double) -> Void) async throws {
        try await channel.send(JSONEncoder().encode(Offer(title: source.title, manifest: source.manifest)))
        guard try await channel.read(limit: 128) == approve else { throw GamePackage.Failure.invalid }
        var done: UInt64 = 0
        var shown = -1
        var frameworkChecked = false
        for file in source.files {
            if file.entry.path.hasPrefix("data/"), !frameworkChecked {
                guard try await channel.read(limit: 128) == ack else { throw GamePackage.Failure.identity }
                frameworkChecked = true
            }
            let before = try file.url.resourceValues(forKeys: [.fileSizeKey, .contentModificationDateKey])
            guard before.fileSize.map(UInt64.init) == file.entry.size, before.contentModificationDate == file.modified else { throw GamePackage.Failure.incomplete }
            let reader = try FileHandle(forReadingFrom: file.url)
            do {
                var left = file.entry.size
                while left > 0 {
                    try Task.checkCancellation()
                    let count = Int(min(UInt64(chunkSize), left))
                    let data = try autoreleasepool { try GamePackage.readExactly(reader, count: count) }
                    try await channel.send(data)
                    guard try await channel.read(limit: 128) == ack else { throw GamePackage.Failure.invalid }
                    left -= UInt64(count); done += UInt64(count)
                    let value = Double(done) / Double(max(1, source.bytes))
                    if Int(value * 100) != shown { shown = Int(value * 100); progress(value) }
                }
                try reader.close()
            } catch { try? reader.close(); throw error }
            // Zero-byte files also require a receiver acknowledgment.
            if file.entry.size == 0 { guard try await channel.read(limit: 128) == ack else { throw GamePackage.Failure.invalid } }
        }
        guard try await channel.read(limit: 128) == finish else { throw GamePackage.Failure.incomplete }
    }

    static func receive(_ sink: PeerGameSink, over channel: PeerGameChannel,
                        progress: @Sendable (Double) -> Void) async throws -> String {
        var checkedFramework = false
        var done: UInt64 = 0
        var shown = -1
        let total = sink.manifest.files.reduce(UInt64(0)) { $0 + $1.size }
        for entry in sink.manifest.files {
            if entry.path.hasPrefix("data/"), !checkedFramework {
                try sink.checkFramework()
                checkedFramework = true
                try await channel.send(ack)
            }
            let target = sink.stage.appendingPathComponent(entry.path)
            try FileManager.default.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            guard FileManager.default.createFile(atPath: target.path, contents: nil) else { throw GamePackage.Failure.invalid }
            let writer = try FileHandle(forWritingTo: target)
            do {
                var left = entry.size
                var digest = SHA256()
                while left > 0 {
                    try Task.checkCancellation()
                    let expected = Int(min(UInt64(chunkSize), left))
                    let data = try await channel.read(limit: expected + 64)
                    guard data.count == expected else { throw GamePackage.Failure.incomplete }
                    try autoreleasepool { try writer.write(contentsOf: data); digest.update(data: data) }
                    left -= UInt64(data.count); done += UInt64(data.count)
                    // Validate each file before releasing the sender to the next one.
                    if left == 0 {
                        try writer.synchronize()
                        guard digest.finalize().map({ String(format: "%02x", $0) }).joined() == entry.sha256 else { throw GamePackage.Failure.incomplete }
                    }
                    try await channel.send(ack)
                    let value = Double(done) / Double(max(1, total))
                    if Int(value * 100) != shown { shown = Int(value * 100); progress(value) }
                }
                if entry.size == 0 {
                    guard SHA256.hash(data: Data()).map({ String(format: "%02x", $0) }).joined() == entry.sha256 else { throw GamePackage.Failure.incomplete }
                    try await channel.send(ack)
                }
                try writer.close()
            } catch { try? writer.close(); throw error }
        }
        try Task.checkCancellation()
        let id = try sink.commit()
        try await channel.send(finish)
        return id
    }
}
