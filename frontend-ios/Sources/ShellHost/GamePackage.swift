import Foundation
import CryptoKit
import ShellUI

/// A deliberately simple streaming container shared with win/game_package.py.
/// No decompression, arbitrary output paths, keys or saved files are accepted.
public enum GamePackage {
    public struct Entry: Codable, Sendable {
        public var path: String
        public var size: UInt64
        public var sha256: String
    }
    public struct Manifest: Codable, Sendable {
        public var schema: Int
        public var titleID: String
        public var bundleID: String
        public var teamID: String
        public var files: [Entry]
    }
    public enum Failure: Error, LocalizedError {
        case invalid, identity, incomplete, space, incompatible, busy
        public var errorDescription: String? {
            switch self {
            case .invalid: hostText("This game package is invalid or unsupported.")
            case .identity: hostText("This game package was signed for another app or account. Export it again for this SpplechOS installation.")
            case .incomplete: hostText("This game package is incomplete or damaged. Export it again.")
            case .space: hostText("There is not enough free space to import this game package.")
            case .incompatible: hostText("This game package does not match this app or its game data.")
            case .busy: hostText("Finish the current operation before importing a game package.")
            }
        }
    }
    struct Journal: Codable {
        var titleID: String
        var names: [String]
        var existing: [String]
        var committed: Bool
    }
    static let owners = ["framework", "romfs.img", "msl", "aoc"]
    static let maxBytes: UInt64 = 100 * 1024 * 1024 * 1024
    static let maxHeader = 32 * 1024 * 1024
    static let chunk = 4 * 1024 * 1024

    static func safePath(_ name: String) -> Bool {
        let parts = name.split(separator: "/", omittingEmptySubsequences: false)
        guard parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." && !$0.contains("\\") && !$0.contains(":") }),
              !name.contains("\0") else { return false }
        return parts.count > 1 && parts[0] == "framework" || name == "data/romfs.img" ||
            parts.count > 2 && parts[0] == "data" && ["msl", "aoc"].contains(String(parts[1]))
    }

    static func readExactly(_ source: FileHandle, count: Int) throws -> Data {
        var result = Data()
        while result.count < count {
            guard let data = try source.read(upToCount: count - result.count), !data.isEmpty else { throw Failure.incomplete }
            result.append(data)
        }
        return result
    }

    /// Validate the entire manifest before creating any output file.
    static func readManifest(_ source: FileHandle, fileSize: UInt64, bundleID: String, teamID: String) throws -> Manifest {
        let prefix = try readExactly(source, count: 16)
        guard prefix.prefix(8) == Data("SPPLPK01".utf8) else { throw Failure.invalid }
        let length = prefix.suffix(8).enumerated().reduce(UInt64(0)) { $0 | UInt64($1.element) << ($1.offset * 8) }
        guard length > 0, length <= maxHeader, length <= fileSize, fileSize >= 16 + length else { throw Failure.invalid }
        let manifest = try JSONDecoder().decode(Manifest.self, from: readExactly(source, count: Int(length)))
        guard manifest.schema == 1, manifest.titleID.range(of: "^[0-9A-F]{16}$", options: .regularExpression) != nil,
              !manifest.files.isEmpty, manifest.files.count <= 200_000 else { throw Failure.invalid }
        guard !teamID.isEmpty, manifest.bundleID == bundleID, manifest.teamID == teamID else { throw Failure.identity }
        var names = Set<String>()
        var bytes: UInt64 = 0
        for entry in manifest.files {
            guard safePath(entry.path), entry.sha256.range(of: "^[0-9a-f]{64}$", options: .regularExpression) != nil,
                  names.insert(entry.path.lowercased()).inserted,
                  entry.size <= maxBytes, bytes <= maxBytes - entry.size else { throw Failure.invalid }
            bytes += entry.size
        }
        // A file cannot also be the parent of another file, even with different casing.
        for name in names {
            var parts = name.split(separator: "/")
            while parts.count > 1 {
                parts.removeLast()
                guard !names.contains(parts.joined(separator: "/")) else { throw Failure.invalid }
            }
        }
        guard bytes == fileSize - 16 - length,
              names.contains("framework/game.manifest.json"), names.contains("data/romfs.img") else { throw Failure.incomplete }
        return manifest
    }

    /// Must run outside the main actor. An import remains invisible until all files pass checks.
    public static func install(from url: URL, dataRoot: URL, frameworksRoot: URL, bundleID: String, teamID: String,
                               environment: HostEnvironment, progress: @Sendable (Double) -> Void = { _ in }) throws -> String {
        let fm = FileManager.default
        try recover(dataRoot: dataRoot, frameworksRoot: frameworksRoot)
        let source = try FileHandle(forReadingFrom: url)
        defer { try? source.close() }
        let fileSize = try source.seekToEnd()
        try source.seek(toOffset: 0)
        let manifest = try readManifest(source, fileSize: fileSize, bundleID: bundleID, teamID: teamID)
        try fm.createDirectory(at: dataRoot, withIntermediateDirectories: true)
        let free = (try fm.attributesOfFileSystem(forPath: dataRoot.path)[.systemFreeSize] as? NSNumber)?.uint64Value ?? 0
        let bytes = manifest.files.reduce(UInt64(0)) { $0 + $1.size }
        guard free >= bytes + 256 * 1024 * 1024 else { throw Failure.space }
        let stage = dataRoot.appendingPathComponent(".package-import-" + UUID().uuidString, isDirectory: true)
        try fm.createDirectory(at: stage, withIntermediateDirectories: false)
        var journalWritten = false
        defer { if !journalWritten { try? fm.removeItem(at: stage) } }
        var done: UInt64 = 0
        for entry in manifest.files {
            try Task.checkCancellation()
            let target = stage.appendingPathComponent(entry.path)
            try fm.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            guard fm.createFile(atPath: target.path, contents: nil) else { throw Failure.invalid }
            let output = try FileHandle(forWritingTo: target)
            do {
                var remaining = entry.size
                var digest = SHA256()
                while remaining > 0 {
                    try Task.checkCancellation()
                    // FileHandle's Foundation bridges create autoreleased buffers.
                    // Retire them per chunk, rather than at the end of a multi-GB import.
                    // Only the byte count escapes this pool, never the file's Data.
                    let copied = try autoreleasepool {
                        let data = try readExactly(source, count: Int(min(UInt64(chunk), remaining)))
                        try output.write(contentsOf: data)
                        digest.update(data: data)
                        return data.count
                    }
                    remaining -= UInt64(copied)
                    done += UInt64(copied)
                    progress(Double(done) / Double(max(1, bytes)))
                }
                try output.synchronize()
                try output.close()
                guard digest.finalize().map({ String(format: "%02x", $0) }).joined() == entry.sha256 else { throw Failure.incomplete }
            } catch { try? output.close(); throw error }
        }
        let framework = stage.appendingPathComponent("framework", isDirectory: true)
        guard let gameJSON = manifest.files.first(where: { $0.path == "framework/game.manifest.json" }),
              gameJSON.size <= 4 * 1024 * 1024 else { throw Failure.invalid }
        let game = try GameManifest.parse(Data(contentsOf: framework.appendingPathComponent("game.manifest.json")))
        guard game.frameworkExecutable == "DmGame\(manifest.titleID)", safePath("framework/" + game.launcher),
              let launcherJSON = manifest.files.first(where: { $0.path == "framework/" + game.launcher }),
              launcherJSON.size <= 4 * 1024 * 1024 else { throw Failure.invalid }
        let profile = try LauncherProfile.parse(Data(contentsOf: framework.appendingPathComponent(game.launcher)))
        guard profile.game == manifest.titleID, game.titleID == manifest.titleID,
              game.framework == "DmGame\(manifest.titleID).framework",
              game.loader == "FH" || environment.chain == nil || environment.chain == game.chain,
              let expected = RomfsIdentity.parse(game.romfsIdentity),
              RomfsIdentity.ofImage(at: stage.appendingPathComponent("data/romfs.img")) == expected else { throw Failure.incompatible }
        let executable = framework.appendingPathComponent(game.frameworkExecutable)
        guard FrameworkSignature.preflightExternal(executable: executable, appBundleURL: Bundle.main.bundleURL, hostTeamID: teamID) == nil else {
            throw Failure.identity
        }
        if let minimum = game.minOSVersion, !isVersion(environment.osVersion, atLeast: minimum) { throw Failure.incompatible }
        guard !ExternalShaders.isRequired(in: framework) ||
              ExternalShaders.hasCompleteTree(at: stage.appendingPathComponent("data/msl")) else { throw Failure.incomplete }
        try fm.setAttributes([.posixPermissions: 0o755], ofItemAtPath: executable.path)
        try fm.createDirectory(at: frameworksRoot, withIntermediateDirectories: true)
        let gameRoot = dataRoot.appendingPathComponent(manifest.titleID, isDirectory: true)
        try fm.createDirectory(at: gameRoot, withIntermediateDirectories: true)
        // Fixed ownership list. No save, setting, backup, log or other game's path can be replaced.
        let names = owners
        let existing = names.filter { fm.fileExists(atPath: destination($0, titleID: manifest.titleID, dataRoot: dataRoot, frameworksRoot: frameworksRoot).path) }
        var journal = Journal(titleID: manifest.titleID, names: names, existing: existing, committed: false)
        try fm.createDirectory(at: stage.appendingPathComponent("previous"), withIntermediateDirectories: false)
        try JSONEncoder().encode(journal).write(to: stage.appendingPathComponent("transaction.json"), options: .atomic)
        journalWritten = true
        do {
            for name in names {
                let target = destination(name, titleID: manifest.titleID, dataRoot: dataRoot, frameworksRoot: frameworksRoot)
                // Symlinked existing game folders must never redirect writes outside Documents.
                try checkParent(name, titleID: manifest.titleID, dataRoot: dataRoot, frameworksRoot: frameworksRoot)
                if existing.contains(name) { try fm.moveItem(at: target, to: stage.appendingPathComponent("previous/" + name)) }
                if fm.fileExists(atPath: staged(name, in: stage).path) {
                    try fm.moveItem(at: staged(name, in: stage), to: target)
                }
            }
            journal.committed = true
            try JSONEncoder().encode(journal).write(to: stage.appendingPathComponent("transaction.json"), options: .atomic)
        } catch {
            try recover(dataRoot: dataRoot, frameworksRoot: frameworksRoot)
            throw error
        }
        try? fm.removeItem(at: stage)
        BackupExclusion.apply(appDataRoot: dataRoot)
        return manifest.titleID
    }

    static func staged(_ name: String, in stage: URL) -> URL {
        stage.appendingPathComponent(name == "framework" ? name : "data/" + name)
    }
    static func destination(_ name: String, titleID: String, dataRoot: URL, frameworksRoot: URL) -> URL {
        name == "framework" ? frameworksRoot.appendingPathComponent("DmGame\(titleID).framework") :
            dataRoot.appendingPathComponent(titleID + "/" + name)
    }

    static func checkParent(_ name: String, titleID: String, dataRoot: URL, frameworksRoot: URL) throws {
        let target = destination(name, titleID: titleID, dataRoot: dataRoot, frameworksRoot: frameworksRoot)
        let expected = name == "framework" ? frameworksRoot.resolvingSymlinksInPath() : dataRoot.resolvingSymlinksInPath().appendingPathComponent(titleID)
        guard target.deletingLastPathComponent().resolvingSymlinksInPath().standardizedFileURL.path == expected.standardizedFileURL.path else { throw Failure.invalid }
    }

    /// Called before catalogue scans, including after an interrupted import.
    public static func recover(dataRoot: URL, frameworksRoot: URL) throws {
        let fm = FileManager.default
        guard fm.fileExists(atPath: dataRoot.path) else { return }
        for name in try fm.contentsOfDirectory(atPath: dataRoot.path) where name.hasPrefix(".package-import-") {
            let stage = dataRoot.appendingPathComponent(name)
            guard (try stage.resourceValues(forKeys: [.isSymbolicLinkKey])).isSymbolicLink != true else { throw Failure.invalid }
            let record = stage.appendingPathComponent("transaction.json")
            guard fm.fileExists(atPath: record.path) else { try fm.removeItem(at: stage); continue }
            guard let size = (try fm.attributesOfItem(atPath: record.path)[.size] as? NSNumber)?.intValue,
                  size <= 64 * 1024 else { throw Failure.invalid }
            let journal = try JSONDecoder().decode(Journal.self, from: Data(contentsOf: record))
            guard journal.titleID.range(of: "^[0-9A-F]{16}$", options: .regularExpression) != nil,
                  Set(journal.names).isSubset(of: Set(owners)), Set(journal.existing).isSubset(of: Set(journal.names)) else { throw Failure.invalid }
            if !journal.committed {
                for name in journal.names.reversed() {
                    try checkParent(name, titleID: journal.titleID, dataRoot: dataRoot, frameworksRoot: frameworksRoot)
                    let target = destination(name, titleID: journal.titleID, dataRoot: dataRoot, frameworksRoot: frameworksRoot)
                    let previous = stage.appendingPathComponent("previous/" + name)
                    if fm.fileExists(atPath: previous.path) {
                        if fm.fileExists(atPath: target.path) { try fm.removeItem(at: target) }
                        try fm.moveItem(at: previous, to: target)
                    } else if !journal.existing.contains(name), !fm.fileExists(atPath: staged(name, in: stage).path), fm.fileExists(atPath: target.path) {
                        try fm.removeItem(at: target)
                    }
                }
            }
            try fm.removeItem(at: stage)
        }
    }
}
