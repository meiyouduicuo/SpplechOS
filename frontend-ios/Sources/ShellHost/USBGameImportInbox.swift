import Foundation

/// Desktop publishes a request only after a complete package has arrived over USB.
public enum USBGameImportInbox {
    public static let folderName = ".usb-game-import"
    public struct Request: Codable, Sendable {
        public var schema: Int
        public var id: String
        public var file: String
    }
    public struct Status: Codable, Sendable {
        public var schema = 1
        public var id: String
        public var state: String
        public var progress: Double
        public var titleID: String?
        public var message: String?
    }
    public static func root(documents: URL) -> URL { documents.appendingPathComponent(folderName, isDirectory: true) }
    public static func pending(in root: URL) -> [(Request, URL)] {
        let fm = FileManager.default
        return ((try? fm.contentsOfDirectory(at: root, includingPropertiesForKeys: [.isSymbolicLinkKey, .fileSizeKey])) ?? [])
            .filter { $0.lastPathComponent.hasSuffix(".request.json") }.sorted { $0.lastPathComponent < $1.lastPathComponent }
            .prefix(128).compactMap { url in
                guard let attrs = try? url.resourceValues(forKeys: [.isSymbolicLinkKey, .fileSizeKey]),
                      attrs.isSymbolicLink != true, let size = attrs.fileSize, size <= 16 * 1024,
                      let data = try? Data(contentsOf: url), let request = try? JSONDecoder().decode(Request.self, from: data),
                      request.schema == 1, let uuid = UUID(uuidString: request.id), uuid.uuidString.lowercased() == request.id,
                      url.lastPathComponent == request.id + ".request.json", request.file == request.id + ".sppgame" else { return nil }
                let receipt = root.appendingPathComponent(request.id + ".status.json")
                if let size = try? receipt.resourceValues(forKeys: [.fileSizeKey]).fileSize, size <= 16 * 1024,
                   let data = try? Data(contentsOf: receipt), let status = try? JSONDecoder().decode(Status.self, from: data),
                   status.id == request.id, status.schema == 1, ["complete", "failed"].contains(status.state) { return nil }
                let package = root.appendingPathComponent(request.file)
                guard let values = try? package.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey]),
                      values.isRegularFile == true, values.isSymbolicLink != true else { return nil }
                return (request, package)
            }
    }
    public static func write(_ status: Status, in root: URL) throws {
        guard let id = UUID(uuidString: status.id), id.uuidString.lowercased() == status.id else { throw GamePackage.Failure.invalid }
        try JSONEncoder().encode(status).write(to: root.appendingPathComponent(status.id + ".status.json"), options: .atomic)
    }
    public static func finish(_ request: Request, in root: URL, titleID: String?, error: String?) throws {
        guard request.file == request.id + ".sppgame", UUID(uuidString: request.id) != nil else { throw GamePackage.Failure.invalid }
        try write(Status(id: request.id, state: error == nil ? "complete" : "failed", progress: error == nil ? 1 : 0,
                         titleID: titleID, message: error), in: root)
        let fm = FileManager.default
        try? fm.removeItem(at: root.appendingPathComponent(request.id + ".request.json"))
        try? fm.removeItem(at: root.appendingPathComponent(request.file))
    }
}
