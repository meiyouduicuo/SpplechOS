import Foundation
import CryptoKit

/// Read-only source files, never a second copy of the installed game or its saves.
struct PeerGameSource: Sendable {
    struct File: Sendable { let entry: GamePackage.Entry; let url: URL; let modified: Date? }
    let manifest: GamePackage.Manifest
    let title: String
    let files: [File]
    var bytes: UInt64 { manifest.files.reduce(0) { $0 + $1.size } }

    static func prepare(entry: CatalogueEntry, image: URL, bundleID: String, teamID: String) throws -> Self {
        guard let game = entry.manifest, let framework = entry.frameworkURL else { throw GamePackage.Failure.invalid }
        let fm = FileManager.default
        var urls: [String: URL] = [:]
        func tree(_ root: URL, prefix: String) throws {
            guard fm.fileExists(atPath: root.path) else { return }
            guard try root.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink != true else { throw GamePackage.Failure.invalid }
            guard let walk = fm.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey]) else { throw GamePackage.Failure.incomplete }
            for case let url as URL in walk {
                try Task.checkCancellation()
                let v = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
                guard v.isSymbolicLink != true else { throw GamePackage.Failure.invalid }
                if v.isRegularFile == true {
                    let relative = String(url.path.dropFirst(root.path.count + 1))
                    urls[prefix + "/" + relative] = url
                }
            }
        }
        try tree(framework, prefix: "framework")
        // Older bundle layouts keep the catalogue metadata outside the framework.
        for name in ["game.manifest.json", game.launcher] where urls["framework/" + name] == nil {
            let url = entry.directory.appendingPathComponent(name)
            if fm.fileExists(atPath: url.path) { urls["framework/" + name] = url }
        }
        for url in [entry.bannerURL, entry.iconURL].compactMap({ $0 }) {
            if url.deletingLastPathComponent().standardizedFileURL == entry.directory.standardizedFileURL {
                urls["framework/" + url.lastPathComponent] = url
            }
        }
        urls["data/romfs.img"] = image
        try tree(image.deletingLastPathComponent().appendingPathComponent("msl"), prefix: "data/msl")
        try tree(image.deletingLastPathComponent().appendingPathComponent("aoc"), prefix: "data/aoc")
        // Framework first: the receiver verifies its real signature before accepting large data files.
        let names = urls.keys.sorted { a, b in
            let af = a.hasPrefix("framework/"), bf = b.hasPrefix("framework/")
            return af == bf ? a < b : af
        }
        var files: [File] = []
        for name in names {
            try Task.checkCancellation()
            guard GamePackage.safePath(name), let url = urls[name] else { throw GamePackage.Failure.invalid }
            let v = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey, .contentModificationDateKey])
            guard v.isRegularFile == true, v.isSymbolicLink != true, let size = v.fileSize, size >= 0 else { throw GamePackage.Failure.invalid }
            let reader = try FileHandle(forReadingFrom: url)
            var digest = SHA256()
            do {
                while true {
                    try Task.checkCancellation()
                    let count = try autoreleasepool {
                        let data = try reader.read(upToCount: PeerGameWire.chunkSize) ?? Data()
                        digest.update(data: data)
                        return data.count
                    }
                    if count == 0 { break }
                }
                try reader.close()
            } catch { try? reader.close(); throw error }
            let e = GamePackage.Entry(path: name, size: UInt64(size), sha256: digest.finalize().map { String(format: "%02x", $0) }.joined())
            files.append(File(entry: e, url: url, modified: v.contentModificationDate))
        }
        let manifest = GamePackage.Manifest(schema: 1, titleID: game.titleID, bundleID: bundleID, teamID: teamID, files: files.map(\.entry))
        let result = Self(manifest: manifest, title: entry.title, files: files)
        try GamePackage.validate(manifest, payloadBytes: result.bytes, bundleID: bundleID, teamID: teamID)
        return result
    }
}

/// Used on one transfer task only. Incoming chunks go straight to the final staging tree.
final class PeerGameSink: @unchecked Sendable {
    let manifest: GamePackage.Manifest
    let stage: URL
    private let dataRoot: URL
    private let frameworksRoot: URL
    private let teamID: String
    private let environment: HostEnvironment
    private var committed = false
    init(manifest: GamePackage.Manifest, dataRoot: URL, frameworksRoot: URL, bundleID: String,
         teamID: String, environment: HostEnvironment) throws {
        let bytes = manifest.files.reduce(UInt64(0)) { value, entry in
            value.addingReportingOverflow(entry.size).overflow ? UInt64.max : value + entry.size
        }
        try GamePackage.validate(manifest, payloadBytes: bytes, bundleID: bundleID, teamID: teamID)
        guard let metadata = manifest.files.first(where: { $0.path == "framework/game.manifest.json" }),
              metadata.size <= 4 * 1024 * 1024 else { throw GamePackage.Failure.invalid }
        // Reject a hostile ordering before receiving anything: executable resources always precede data.
        guard let firstData = manifest.files.firstIndex(where: { $0.path.hasPrefix("data/") }), firstData > 0,
              manifest.files[..<firstData].allSatisfy({ $0.path.hasPrefix("framework/") }),
              manifest.files[firstData...].allSatisfy({ $0.path.hasPrefix("data/") }) else { throw GamePackage.Failure.invalid }
        let fm = FileManager.default
        try fm.createDirectory(at: dataRoot, withIntermediateDirectories: true)
        let free = (try fm.attributesOfFileSystem(forPath: dataRoot.path)[.systemFreeSize] as? NSNumber)?.uint64Value ?? 0
        guard bytes <= GamePackage.maxBytes, free >= bytes + 256 * 1024 * 1024 else { throw GamePackage.Failure.space }
        self.manifest = manifest; self.dataRoot = dataRoot; self.frameworksRoot = frameworksRoot
        self.teamID = teamID; self.environment = environment
        stage = dataRoot.appendingPathComponent(".package-import-" + UUID().uuidString)
        try fm.createDirectory(at: stage, withIntermediateDirectories: false)
    }
    deinit {
        // A committed journal belongs to crash recovery; never discard rollback resources here.
        if !committed, !FileManager.default.fileExists(atPath: stage.appendingPathComponent("transaction.json").path) {
            try? FileManager.default.removeItem(at: stage)
        }
    }
    func checkFramework() throws {
        let root = stage.appendingPathComponent("framework")
        let game = try GameManifest.parse(Data(contentsOf: root.appendingPathComponent("game.manifest.json")))
        guard game.titleID == manifest.titleID, game.frameworkExecutable == "DmGame" + manifest.titleID,
              GamePackage.safePath("framework/" + game.launcher),
              game.loader == "FH" || environment.chain == nil || game.chain == environment.chain,
              FrameworkSignature.preflightExternal(executable: root.appendingPathComponent(game.frameworkExecutable),
                  appBundleURL: Bundle.main.bundleURL, hostTeamID: teamID) == nil else { throw GamePackage.Failure.identity }
        if let minimum = game.minOSVersion, !isVersion(environment.osVersion, atLeast: minimum) { throw GamePackage.Failure.incompatible }
    }
    func commit() throws -> String {
        let id = try GamePackage.commitStage(manifest, stage: stage, dataRoot: dataRoot,
            frameworksRoot: frameworksRoot, teamID: teamID, environment: environment)
        committed = true
        return id
    }
}
