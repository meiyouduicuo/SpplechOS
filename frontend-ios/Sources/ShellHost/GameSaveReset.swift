import Foundation

/// Clears the engine's current save trees and their transaction/sync sidecars.
/// Save backups have a separate name and stay available for an explicit restore.
public enum GameSaveReset {
    public static func isCurrentSave(_ name: String) -> Bool {
        name == "save" || name.hasPrefix("save.") || name == "save_device" || name.hasPrefix("save_device.")
    }

    /// A process interruption during a confirmed reset must not launch a partially cleared save.
    public static func finishPendingReset(in folder: URL, fileManager fm: FileManager = .default) throws {
        guard fm.fileExists(atPath: folder.path) else { return }
        let names = try fm.contentsOfDirectory(atPath: folder.path)
        if names.contains(where: { $0.hasPrefix(".cleared-saves-") }) {
            try clear(in: folder, fileManager: fm)
        }
    }

    public static func clear(in folder: URL, fileManager fm: FileManager = .default) throws {
        guard fm.fileExists(atPath: folder.path) else { return }
        guard try folder.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink != true else {
            throw CocoaError(.fileWriteNoPermission)
        }
        let names = try fm.contentsOfDirectory(atPath: folder.path)
        // A previous reset may have finished moving the saves but failed to remove its staging folder.
        for name in names where name.hasPrefix(".cleared-saves-") {
            try fm.removeItem(at: folder.appendingPathComponent(name))
        }
        let saves = names.filter(isCurrentSave).sorted()
        guard !saves.isEmpty else { return }
        let stage = folder.appendingPathComponent(".cleared-saves-\(UUID().uuidString)", isDirectory: true)
        try fm.createDirectory(at: stage, withIntermediateDirectories: false)
        var moved: [String] = []
        do {
            for name in saves {
                try fm.moveItem(at: folder.appendingPathComponent(name), to: stage.appendingPathComponent(name))
                moved.append(name)
            }
        } catch {
            let moveError = error
            for name in moved.reversed() {
                try fm.moveItem(at: stage.appendingPathComponent(name), to: folder.appendingPathComponent(name))
            }
            try fm.removeItem(at: stage)
            throw moveError
        }
        try fm.removeItem(at: stage)
    }
}
