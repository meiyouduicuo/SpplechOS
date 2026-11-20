import Foundation
import Testing
@testable import ShellHost

struct USBGameImportInboxTests {
    @Test func incompleteTransfersAreIgnoredAndCompletionOnlyRemovesOwnedFiles() throws {
        let box = try Sandbox()
        let fm = FileManager.default
        let root = USBGameImportInbox.root(documents: box.root)
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        let id = UUID().uuidString.lowercased()
        let request = USBGameImportInbox.Request(schema: 1, id: id, file: id + ".sppgame")
        let requestURL = root.appendingPathComponent(id + ".request.json")
        let package = root.appendingPathComponent(request.file)
        let save = box.root.appendingPathComponent("save.dat")
        try Data("keep save".utf8).write(to: save)
        try JSONEncoder().encode(request).write(to: requestURL)
        #expect(USBGameImportInbox.pending(in: root).isEmpty)
        try Data("package".utf8).write(to: package)
        #expect(USBGameImportInbox.pending(in: root).count == 1)
        try USBGameImportInbox.finish(request, in: root, titleID: Fixtures.orbit, error: nil)
        #expect(USBGameImportInbox.pending(in: root).isEmpty)
        #expect(!fm.fileExists(atPath: package.path))
        #expect(!fm.fileExists(atPath: requestURL.path))
        let status = try JSONDecoder().decode(USBGameImportInbox.Status.self,
            from: Data(contentsOf: root.appendingPathComponent(id + ".status.json")))
        #expect(status.state == "complete" && status.titleID == Fixtures.orbit)
        #expect(try String(contentsOf: save, encoding: .utf8) == "keep save")
    }

    @Test func requestsCannotEscapeInboxOrImportSymlinks() throws {
        let box = try Sandbox()
        let fm = FileManager.default
        let root = USBGameImportInbox.root(documents: box.root)
        try fm.createDirectory(at: root, withIntermediateDirectories: true)
        let id = UUID().uuidString.lowercased()
        let requestURL = root.appendingPathComponent(id + ".request.json")
        let bad = USBGameImportInbox.Request(schema: 1, id: id, file: "../save.dat")
        try JSONEncoder().encode(bad).write(to: requestURL)
        #expect(USBGameImportInbox.pending(in: root).isEmpty)
        let good = USBGameImportInbox.Request(schema: 1, id: id, file: id + ".sppgame")
        try JSONEncoder().encode(good).write(to: requestURL)
        let outside = box.root.appendingPathComponent("save.dat")
        try Data("keep".utf8).write(to: outside)
        try fm.createSymbolicLink(at: root.appendingPathComponent(good.file), withDestinationURL: outside)
        #expect(USBGameImportInbox.pending(in: root).isEmpty)
        #expect(try String(contentsOf: outside, encoding: .utf8) == "keep")
    }

    @Test func completedReceiptPreventsReimportAfterInterruptedCleanup() throws {
        let box = try Sandbox()
        let root = USBGameImportInbox.root(documents: box.root)
        try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        let id = UUID().uuidString.lowercased()
        let request = USBGameImportInbox.Request(schema: 1, id: id, file: id + ".sppgame")
        try Data("package".utf8).write(to: root.appendingPathComponent(request.file))
        try JSONEncoder().encode(request).write(to: root.appendingPathComponent(id + ".request.json"))
        try USBGameImportInbox.write(.init(id: id, state: "complete", progress: 1, titleID: Fixtures.orbit), in: root)
        #expect(USBGameImportInbox.pending(in: root).isEmpty)
    }
}
