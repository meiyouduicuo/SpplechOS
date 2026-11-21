import Foundation
import CryptoKit
import Darwin
import Testing
@testable import ShellHost

struct GamePackageMemoryTests {
    /// Exercise the real extraction and hashing loop on a sparse synthetic image.
    /// A tiny invalid game manifest stops before commit, so no executable is needed.
    @Test func largePackageExtractionKeepsMemoryBoundedAndPreservesSaves() throws {
        let box = try Sandbox()
        let fm = FileManager.default
        let size = 512 * 1024 * 1024
        let zero = Data(repeating: 0, count: 1024 * 1024)
        var hash = SHA256()
        for _ in 0..<(size / zero.count) { hash.update(data: zero) }
        let digest = hash.finalize().map { String(format: "%02x", $0) }.joined()
        let invalidJSON = Data("{}".utf8)
        let entries = [GamePackage.Entry(path: "data/romfs.img", size: UInt64(size), sha256: digest),
                       GamePackage.Entry(path: "framework/game.manifest.json", size: 2,
                           sha256: SHA256.hash(data: invalidJSON).map { String(format: "%02x", $0) }.joined())]
        let manifest = GamePackage.Manifest(schema: 1, titleID: Fixtures.orbit, bundleID: "org.spplechos.shell",
                                           teamID: "TEAM123456", files: entries)
        let json = try JSONEncoder().encode(manifest)
        var header = Data("SPPLPK01".utf8)
        var length = UInt64(json.count).littleEndian
        withUnsafeBytes(of: &length) { header.append(contentsOf: $0) }
        header.append(json)
        let package = box.root.appendingPathComponent("large.sppgame")
        #expect(fm.createFile(atPath: package.path, contents: nil))
        let writer = try FileHandle(forWritingTo: package)
        try writer.write(contentsOf: header)
        try writer.seek(toOffset: UInt64(header.count + size))
        try writer.write(contentsOf: invalidJSON)
        try writer.close()
        let save = box.appData.appendingPathComponent(Fixtures.orbit + "/save/main.dat")
        try fm.createDirectory(at: save.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data("keep this save".utf8).write(to: save)

        let samples = MemorySamples()
        var rejected = false
        do {
            _ = try GamePackage.install(from: package, dataRoot: box.appData,
                frameworksRoot: box.root.appendingPathComponent("hot"), bundleID: manifest.bundleID,
                teamID: manifest.teamID, environment: HostEnvironment(chain: "b-3f9a2c"),
                progress: { value in samples.record(value) })
        } catch { rejected = true }
        let growth = samples.peak - min(samples.baseline, samples.peak)
        print("[package-memory] bytes=\(size) baseline=\(samples.baseline) peak=\(samples.peak) growth=\(growth) progress=\(samples.progress)")
        #expect(rejected)
        #expect(samples.progress >= 0.99, "The test must exercise the entire large extraction")
        #expect(growth < 192 * 1024 * 1024, "Streaming extraction must not retain a growing set of file buffers")
        #expect(try String(contentsOf: save, encoding: .utf8) == "keep this save")
        #expect(try fm.contentsOfDirectory(atPath: box.appData.path).allSatisfy { !$0.hasPrefix(".package-import-") })
    }
}

private final class MemorySamples: @unchecked Sendable {
    let baseline = MemorySamples.residentBytes()
    private(set) var peak: UInt64 = 0
    private(set) var progress: Double = 0
    func record(_ value: Double) {
        peak = max(peak, Self.residentBytes())
        progress = value
    }
    static func residentBytes() -> UInt64 {
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
