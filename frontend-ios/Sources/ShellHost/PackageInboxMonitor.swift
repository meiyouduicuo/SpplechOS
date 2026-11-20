import Foundation
import Dispatch
import Darwin

/// A filesystem event wakes the importer. No periodic UI or directory polling.
final class PackageInboxMonitor: @unchecked Sendable {
    private let source: any DispatchSourceFileSystemObject
    init(root: URL, changed: @escaping @Sendable () -> Void) throws {
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let descriptor = open(root.path, O_EVTONLY)
        guard descriptor >= 0 else { throw CocoaError(.fileReadUnknown) }
        source = DispatchSource.makeFileSystemObjectSource(fileDescriptor: descriptor, eventMask: [.write, .rename, .delete], queue: .global(qos: .utility))
        source.setEventHandler(handler: changed)
        source.setCancelHandler { close(descriptor) }
        source.resume()
    }
    deinit { source.cancel() }
}
