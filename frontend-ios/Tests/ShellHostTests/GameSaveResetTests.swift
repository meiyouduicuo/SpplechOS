import Foundation
import Testing
@testable import ShellHost

private final class FailingSaveMove: FileManager, @unchecked Sendable {
    override func moveItem(at source: URL, to destination: URL) throws {
        if source.lastPathComponent == "save.work" && destination.deletingLastPathComponent().lastPathComponent.hasPrefix(".cleared-saves-") {
            throw CocoaError(.fileWriteNoPermission)
        }
        try super.moveItem(at: source, to: destination)
    }
}

@MainActor @Suite struct GameSaveResetTests {
    @Test func clearsOnlyCurrentSaveTreesAndPreservesBackupsAndGameData() throws {
        let box = try Sandbox()
        let folder = try box.giveAppData()
        let removed = ["save/0/file.bin", "save_device/0/file.bin", "save.work/0/file.bin", "save.new/0/file.bin",
                       "save_device.work/0/file.bin", "save_device.new/0/file.bin", "save.sync", "save.sync.tmp"]
        let kept = ["save-backups/old.dmsync", "romfs.img", "aoc/1000.img", "msl/b-test.img", "temp/file.bin", "env.txt"]
        for file in removed + kept { try box.write("fixture", to: folder.appendingPathComponent(file)) }
        let other = box.appData.appendingPathComponent(Fixtures.chain).appendingPathComponent("save/0/file.bin")
        try box.write("other game", to: other)
        try GameSaveReset.clear(in: folder)
        for file in removed { #expect(!FileManager.default.fileExists(atPath: folder.appendingPathComponent(file).path)) }
        for file in kept { #expect(try String(contentsOf: folder.appendingPathComponent(file), encoding: .utf8) == "fixture") }
        #expect(try String(contentsOf: other, encoding: .utf8) == "other game")
        try GameSaveReset.clear(in: folder)
    }

    @Test func aFailedMoveRestoresTheCurrentSave() throws {
        let box = try Sandbox()
        let folder = try box.giveAppData()
        for file in ["save/0/file.bin", "save.work/0/file.bin"] {
            try box.write("original", to: folder.appendingPathComponent(file))
        }
        #expect(throws: CocoaError.self) { try GameSaveReset.clear(in: folder, fileManager: FailingSaveMove()) }
        for file in ["save/0/file.bin", "save.work/0/file.bin"] {
            #expect(try String(contentsOf: folder.appendingPathComponent(file), encoding: .utf8) == "original")
        }
    }

    @Test func actionsKeepTheGamePlayableAndDisableInheritedCloudSync() throws {
        let box = try Sandbox()
        let folder = try box.giveAppData()
        try box.write("current", to: folder.appendingPathComponent("save/0/file.bin"))
        let model = ShellHostModel(config: box.config())
        model.actions.onClearGameSaves(Fixtures.orbit)
        #expect(box.defaults(Fixtures.orbit).bool(forKey: GameDefaults.cloudSavesOffKey))
        #expect(!FileManager.default.fileExists(atPath: folder.appendingPathComponent("save").path))
        #expect(model.details.first { $0.id == Fixtures.orbit }?.game.state == .playable)
        #expect(box.defaults(Fixtures.orbit).string(forKey: GameDeletion.deletedKey) == nil)
        #expect(model.notice != nil)
    }

    @Test func missingSaveFolderAndUnknownGameAreSafe() throws {
        let box = try Sandbox()
        try GameSaveReset.clear(in: box.appData.appendingPathComponent("missing"))
        let model = ShellHostModel(config: box.config())
        model.clearGameSaves("not-a-game")
        #expect(model.notice == nil)
    }

    @Test func aLinkedGameFolderIsRejected() throws {
        let box = try Sandbox()
        let outside = box.root.appendingPathComponent("another-app")
        let original = outside.appendingPathComponent("save/0/file.bin")
        try box.write("original", to: original)
        let link = box.appData.appendingPathComponent("linked-game")
        try FileManager.default.createSymbolicLink(at: link, withDestinationURL: outside)
        #expect(throws: CocoaError.self) { try GameSaveReset.clear(in: link) }
        #expect(try String(contentsOf: original, encoding: .utf8) == "original")
    }

    @Test func anInterruptedResetIsFinishedBeforeTheNextLaunch() throws {
        let box = try Sandbox()
        let folder = try box.giveAppData()
        try box.write("staged", to: folder.appendingPathComponent(".cleared-saves-fixture/save/0/file.bin"))
        try box.write("remaining", to: folder.appendingPathComponent("save_device/0/file.bin"))
        try GameSaveReset.finishPendingReset(in: folder)
        #expect(!FileManager.default.fileExists(atPath: folder.appendingPathComponent("save_device").path))
        #expect(!FileManager.default.fileExists(atPath: folder.appendingPathComponent(".cleared-saves-fixture").path))
        #expect(FileManager.default.fileExists(atPath: folder.appendingPathComponent("romfs/fixture.marker").path))
    }
}
