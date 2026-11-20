import Foundation
import Testing
@testable import ShellHost

struct GamePackageTests {
    let bundleID = "org.spplechos.shell"
    let teamID = "TEAM123456"
    var fixture: URL { Bundle.module.url(forResource: "Fixtures", withExtension: nil)!.appendingPathComponent("GamePackage/synthetic.sppgame") }

    func install(_ url: URL, box: Sandbox, team: String = "TEAM123456") throws -> String {
        try GamePackage.install(from: url, dataRoot: box.appData, frameworksRoot: box.root.appendingPathComponent("hot"),
                                bundleID: bundleID, teamID: team, environment: HostEnvironment(chain: "b-3f9a2c"))
    }

    @Test func pythonPackageImportsAndReimportsWithoutTouchingSavesOrOtherGames() throws {
        let box = try Sandbox()
        let fm = FileManager.default
        let saves = box.appData.appendingPathComponent(Fixtures.orbit + "/save/main.dat")
        let other = box.appData.appendingPathComponent(Fixtures.chain + "/save/main.dat")
        for url in [saves, other] {
            try fm.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
            try Data("keep this save".utf8).write(to: url)
        }
        let first = try install(fixture, box: box)
        #expect(first == Fixtures.orbit)
        let fw = box.root.appendingPathComponent("hot/DmGame\(first).framework")
        #expect(GameCatalogue.readFramework(at: fw).problem == nil)
        #expect(FrameworkSignature.inspect(executable: fw.appendingPathComponent("DmGame" + first))?.teamID == teamID)
        #expect(try Data(contentsOf: saves) == Data("keep this save".utf8))
        let second = try install(fixture, box: box)
        #expect(second == first)
        for url in [saves, other] { #expect(try String(contentsOf: url, encoding: .utf8) == "keep this save") }
        #expect(try fm.contentsOfDirectory(atPath: box.appData.path).allSatisfy { !$0.hasPrefix(".package-import-") })
    }

    @Test func corruptPackageAndWrongSigningTeamLeaveInstalledGameIntact() throws {
        let box = try Sandbox()
        _ = try install(fixture, box: box)
        let target = box.appData.appendingPathComponent(Fixtures.orbit + "/romfs.img")
        let before = try Data(contentsOf: target)
        var bytes = try Data(contentsOf: fixture)
        bytes[bytes.count - 1] ^= 1
        let broken = box.root.appendingPathComponent("broken.sppgame")
        try bytes.write(to: broken)
        #expect(throws: GamePackage.Failure.self) { try install(broken, box: box) }
        #expect(throws: GamePackage.Failure.self) { try install(fixture, box: box, team: "OTHER") }
        #expect(try Data(contentsOf: target) == before)
        #expect(GameCatalogue.scan(root: box.root.appendingPathComponent("hot")).count == 1)
    }

    @Test func truncatedAndTrailingBytesNeverPublishANewGame() throws {
        for transform in [0, 1] {
            let box = try Sandbox()
            var bytes = try Data(contentsOf: fixture)
            if transform == 0 { bytes.removeLast() } else { bytes.append(0) }
            let broken = box.root.appendingPathComponent("broken.sppgame")
            try bytes.write(to: broken)
            #expect(throws: GamePackage.Failure.self) { try install(broken, box: box) }
            #expect(!FileManager.default.fileExists(atPath: box.root.appendingPathComponent("hot").path))
        }
    }

    @Test func rejectsTraversalSavedFilesCaseCollisionsAndFileParentCollisions() throws {
        for name in ["data/save/main.dat", "framework/../save", "/framework/foo", "framework/C:x", "framework/a\\b", "data/msl//a"] {
            #expect(!GamePackage.safePath(name))
        }
        #expect(GamePackage.safePath("framework/封面.jpg"))
        for paths in [["framework/A", "framework/a"], ["framework/a", "framework/A/child"]] {
            let box = try Sandbox()
            let entries = (["data/romfs.img", "framework/game.manifest.json"] + paths).map {
                GamePackage.Entry(path: $0, size: 1, sha256: String(repeating: "0", count: 64))
            }
            let url = box.root.appendingPathComponent("header")
            let manifest = GamePackage.Manifest(schema: 1, titleID: Fixtures.orbit, bundleID: bundleID, teamID: teamID, files: entries)
            let encoded = try header(manifest)
            try encoded.write(to: url)
            let source = try FileHandle(forReadingFrom: url)
            defer { try? source.close() }
            #expect(throws: GamePackage.Failure.self) {
                try GamePackage.readManifest(source, fileSize: UInt64(encoded.count + entries.count), bundleID: bundleID, teamID: teamID)
            }
        }
    }

    @Test func sizesLargerThanFourGiBAreNotTruncated() throws {
        let box = try Sandbox()
        let entries = [GamePackage.Entry(path: "data/romfs.img", size: 5 * 1024 * 1024 * 1024, sha256: String(repeating: "0", count: 64)),
                       GamePackage.Entry(path: "framework/game.manifest.json", size: 1, sha256: String(repeating: "0", count: 64))]
        let manifest = GamePackage.Manifest(schema: 1, titleID: Fixtures.orbit, bundleID: bundleID, teamID: teamID, files: entries)
        let encoded = try header(manifest)
        let url = box.root.appendingPathComponent("header")
        try encoded.write(to: url)
        let source = try FileHandle(forReadingFrom: url)
        defer { try? source.close() }
        let read = try GamePackage.readManifest(source, fileSize: UInt64(encoded.count) + entries[0].size + 1, bundleID: bundleID, teamID: teamID)
        #expect(read.files[0].size == 5 * 1024 * 1024 * 1024)
    }

    @Test func interruptedReplacementRollsBackAndCommittedReplacementStays() throws {
        for committed in [false, true] {
            let box = try Sandbox()
            let fm = FileManager.default
            let stage = box.appData.appendingPathComponent(".package-import-" + UUID().uuidString)
            let game = box.appData.appendingPathComponent(Fixtures.orbit)
            try fm.createDirectory(at: stage.appendingPathComponent("previous"), withIntermediateDirectories: true)
            try fm.createDirectory(at: game.appendingPathComponent("save"), withIntermediateDirectories: true)
            try Data("old image".utf8).write(to: stage.appendingPathComponent("previous/romfs.img"))
            try Data("new image".utf8).write(to: game.appendingPathComponent("romfs.img"))
            try Data("save".utf8).write(to: game.appendingPathComponent("save/main.dat"))
            let journal = GamePackage.Journal(titleID: Fixtures.orbit, names: ["romfs.img"], existing: ["romfs.img"], committed: committed)
            try JSONEncoder().encode(journal).write(to: stage.appendingPathComponent("transaction.json"))
            try GamePackage.recover(dataRoot: box.appData, frameworksRoot: box.root.appendingPathComponent("hot"))
            #expect(try String(contentsOf: game.appendingPathComponent("romfs.img"), encoding: .utf8) == (committed ? "new image" : "old image"))
            #expect(try String(contentsOf: game.appendingPathComponent("save/main.dat"), encoding: .utf8) == "save")
            #expect(!fm.fileExists(atPath: stage.path))
        }
    }

    private func header(_ manifest: GamePackage.Manifest) throws -> Data {
        let json = try JSONEncoder().encode(manifest)
        var length = UInt64(json.count).littleEndian
        var data = Data("SPPLPK01".utf8)
        withUnsafeBytes(of: &length) { data.append(contentsOf: $0) }
        data.append(json)
        return data
    }
}
