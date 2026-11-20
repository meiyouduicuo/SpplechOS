import Foundation
#if canImport(UIKit)
import UIKit
#endif

extension ShellHostModel {
    func startUSBGameImports() {
        guard config.hotFrameworksRoot != nil else { return }
        let root = USBGameImportInbox.root(documents: config.appDataRoot.deletingLastPathComponent())
        do {
            usbInboxMonitor = try PackageInboxMonitor(root: root) { [weak self] in
                Task { @MainActor in self?.scheduleUSBImport() }
            }
        } catch { notice = error.localizedDescription }
        #if canImport(UIKit)
        usbActiveObserver = NotificationCenter.default.addObserver(forName: UIApplication.didBecomeActiveNotification, object: nil, queue: .main) { [weak self] _ in
            Task { @MainActor in self?.scheduleUSBImport() }
        }
        #endif
        scheduleUSBImport()
    }

    func scheduleUSBImport() {
        guard usbImportTask == nil, acceptsUSBImport, config.hotFrameworksRoot != nil else { return }
        #if canImport(UIKit)
        guard UIApplication.shared.applicationState == .active else { return }
        #endif
        let root = USBGameImportInbox.root(documents: config.appDataRoot.deletingLastPathComponent())
        guard let (request, package) = USBGameImportInbox.pending(in: root).first else { return }
        usbImportTask = Task { [weak self] in
            guard let self else { return }
            var finalized = false
            defer {
                self.usbImportTask = nil
                if finalized { self.scheduleUSBImport() }
            }
            let emitter = USBImportProgress(id: request.id, root: root)
            do {
                try USBGameImportInbox.write(.init(id: request.id, state: "importing", progress: 0), in: root)
                let id = try await self.importGamePackageNow(package) { value in emitter.update(value) }
                // importGamePackageNow reloads the catalogue before returning.
                try USBGameImportInbox.finish(request, in: root, titleID: id, error: nil)
                finalized = true
            } catch {
                do {
                    try USBGameImportInbox.finish(request, in: root, titleID: nil, error: error.localizedDescription)
                    finalized = true
                } catch { /* A later foreground event can retry after storage becomes available. */ }
                self.notice = error.localizedDescription
            }
        }
    }
}

private final class USBImportProgress: @unchecked Sendable {
    let id: String
    let root: URL
    private let lock = NSLock()
    private var percent = -1
    init(id: String, root: URL) { self.id = id; self.root = root }
    func update(_ value: Double) {
        lock.lock()
        defer { lock.unlock() }
        let next = Int(value * 100)
        guard next != percent else { return }
        percent = next
        try? USBGameImportInbox.write(.init(id: id, state: "importing", progress: value), in: root)
    }
}
