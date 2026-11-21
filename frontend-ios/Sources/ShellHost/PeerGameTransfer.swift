import Foundation
import Observation
@preconcurrency import Network
#if canImport(UIKit)
import UIKit
#endif

struct NearbyGameDevice: Identifiable, Sendable {
    let id: String
    let name: String
    let endpoint: NWEndpoint
}

/// Discovery exists only while this sheet is open; receiving always requires consent.
@MainActor @Observable final class PeerGameTransfer: Identifiable {
    enum Mode { case send(@MainActor @Sendable () async throws -> PeerGameSource), receive }
    enum Phase { case searching, connecting, pairing, preparing, waiting, offer, transferring, complete, failed }
    let id = UUID()
    let mode: Mode
    var phase: Phase = .searching
    var devices: [NearbyGameDevice] = []
    var code = ""
    var peerName = ""
    var gameTitle = ""
    var offeredBytes: UInt64 = 0
    var progress = 0.0
    var message = ""
    private let config: ShellHostConfig
    private let bundleID: String
    private let teamID: String
    private let completed: @MainActor (String) -> Void
    @ObservationIgnored private var browser: NWBrowser?
    @ObservationIgnored private var listener: NWListener?
    @ObservationIgnored private var channel: PeerGameChannel?
    @ObservationIgnored private var work: Task<Void, Never>?
    @ObservationIgnored private var deadline: Task<Void, Never>?
    @ObservationIgnored private var decision: CheckedContinuation<Bool, Never>?
    @ObservationIgnored private var lastProgress = Date()
    @ObservationIgnored private var idleTimerWasDisabled = false
    @ObservationIgnored private var hasStarted = false
    var sending: Bool { if case .send = mode { return true }; return false }

    init(mode: Mode, config: ShellHostConfig, bundleID: String, teamID: String,
         completed: @escaping @MainActor (String) -> Void) {
        self.mode = mode; self.config = config; self.bundleID = bundleID
        self.teamID = teamID; self.completed = completed
    }
    func start() {
        guard phase == .searching, !hasStarted, browser == nil, listener == nil, work == nil else { return }
        hasStarted = true
        #if canImport(UIKit)
        idleTimerWasDisabled = UIApplication.shared.isIdleTimerDisabled
        UIApplication.shared.isIdleTimerDisabled = true
        #endif
        do {
            guard !bundleID.isEmpty, !teamID.isEmpty else { throw GamePackage.Failure.identity }
            let parameters = NWParameters.tcp
            parameters.includePeerToPeer = true
            if sending {
                let search = NWBrowser(for: .bonjour(type: "_spp-game._tcp", domain: nil), using: parameters)
                search.browseResultsChangedHandler = { [weak self] results, _ in
                    let devices = results.compactMap { result -> NearbyGameDevice? in
                        guard case let .service(name, _, _, _) = result.endpoint else { return nil }
                        return NearbyGameDevice(id: result.endpoint.debugDescription, name: name, endpoint: result.endpoint)
                    }.sorted { $0.name < $1.name }
                    Task { @MainActor [weak self] in self?.devices = devices }
                }
                search.stateUpdateHandler = { [weak self] state in
                    if case .failed(let error) = state { Task { @MainActor [weak self] in self?.fail(error) } }
                }
                browser = search; search.start(queue: .main)
            } else {
                let server = try NWListener(using: parameters)
                #if canImport(UIKit)
                let name = UIDevice.current.name
                #else
                let name = Host.current().localizedName ?? "SpplechOS"
                #endif
                server.service = .init(name: String(name.prefix(40)) + " · " + String(id.uuidString.prefix(4)), type: "_spp-game._tcp")
                server.newConnectionHandler = { [weak self] connection in
                    Task { @MainActor [weak self] in
                        guard let self, self.channel == nil, self.phase == .searching else { connection.cancel(); return }
                        self.connect(connection, name: "")
                    }
                }
                server.stateUpdateHandler = { [weak self] state in
                    if case .failed(let error) = state { Task { @MainActor [weak self] in self?.fail(error) } }
                }
                listener = server; server.start(queue: .main)
            }
            // No payload or automatic acceptance is possible while waiting for a device.
        } catch { fail(error) }
    }
    func choose(_ device: NearbyGameDevice) {
        guard phase == .searching, sending else { return }
        connect(NWConnection(to: device.endpoint, using: { let p = NWParameters.tcp; p.includePeerToPeer = true; return p }()), name: device.name)
    }
    private func connect(_ connection: NWConnection, name: String) {
        browser?.cancel(); browser = nil
        phase = .connecting; peerName = name
        let channel = PeerGameChannel(connection)
        self.channel = channel
        lastProgress = Date()
        deadline = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(5))
                guard !Task.isCancelled, let self else { return }
                // Allow time to compare codes and accept the offer, but bound abandoned sessions.
                let limit: TimeInterval = self.phase == .preparing ? 1800 : self.phase == .pairing || self.phase == .offer || self.phase == .waiting ? 300 : 120
                if Date().timeIntervalSince(self.lastProgress) > limit {
                    self.fail(NSError(domain: "SpplechOS", code: 1,
                        userInfo: [NSLocalizedDescriptionKey: hostText("The connection timed out. Keep both apps open and try again.")]))
                    return
                }
            }
        }
        work = Task { [weak self] in
            guard let self else { return }
            do {
                try await channel.start()
                self.code = try await channel.handshake(bundleID: self.bundleID, teamID: self.teamID)
                self.phase = .pairing
                guard await self.ask() else { throw CancellationError() }
                try await channel.send(PeerGameWire.approve)
                guard try await channel.read(limit: 128) == PeerGameWire.approve else { throw GamePackage.Failure.invalid }
                self.lastProgress = Date()
                self.phase = .preparing
                let update: @Sendable (Double) -> Void = { [weak self] value in
                    Task { @MainActor in self?.progress = value; self?.lastProgress = Date(); if self?.phase == .waiting { self?.phase = .transferring } }
                }
                switch self.mode {
                case .send(let prepare):
                    let source = try await prepare()
                    try Task.checkCancellation()
                    self.gameTitle = source.title; self.offeredBytes = source.bytes
                    self.phase = .waiting
                    let sending = Task.detached {
                        try await PeerGameWire.send(source, over: channel, progress: update)
                    }
                    try await withTaskCancellationHandler { try await sending.value } onCancel: { sending.cancel(); channel.cancel() }
                case .receive:
                    let data = try await channel.read()
                    let offer = try JSONDecoder().decode(PeerGameWire.Offer.self, from: data)
                    guard offer.title.count <= 512, let hot = self.config.hotFrameworksRoot else { throw GamePackage.Failure.invalid }
                    // Validate and check free space before asking to receive, without creating an archive.
                    let config = self.config, bundleID = self.bundleID, teamID = self.teamID
                    let sink = try PeerGameSink(manifest: offer.manifest, dataRoot: config.appDataRoot,
                        frameworksRoot: hot, bundleID: bundleID, teamID: teamID, environment: config.environment)
                    self.gameTitle = offer.title
                    self.offeredBytes = offer.manifest.files.reduce(0) { $0 + $1.size }
                    self.phase = .offer; self.lastProgress = Date()
                    guard await self.ask() else { throw CancellationError() }
                    self.phase = .transferring
                    try await channel.send(PeerGameWire.approve)
                    let receiving = Task.detached {
                        try await PeerGameWire.receive(sink, over: channel, progress: update)
                    }
                    let titleID = try await withTaskCancellationHandler { try await receiving.value } onCancel: { receiving.cancel(); channel.cancel() }
                    self.completed(titleID)
                }
                self.progress = 1; self.phase = .complete
                self.deadline?.cancel(); self.deadline = nil
                self.listener?.cancel(); self.listener = nil
                self.work = nil
                // Keep the final acknowledgment alive until the peer closes or the sheet is dismissed.
            } catch {
                guard self.phase != .failed else { return }
                self.fail(error)
            }
        }
    }
    private func ask() async -> Bool {
        await withCheckedContinuation { decision = $0 }
    }
    func confirm() { let pending = decision; decision = nil; lastProgress = Date(); pending?.resume(returning: true) }
    func stop() {
        decision?.resume(returning: false); decision = nil
        work?.cancel(); work = nil; deadline?.cancel(); deadline = nil
        channel?.cancel(); channel = nil
        browser?.cancel(); browser = nil; listener?.cancel(); listener = nil
        #if canImport(UIKit)
        UIApplication.shared.isIdleTimerDisabled = idleTimerWasDisabled
        #endif
    }
    private func fail(_ error: Error) {
        guard phase != .failed else { return }
        message = error is CancellationError ? hostText("Transfer cancelled.") : error.localizedDescription
        phase = .failed
        stop()
    }
}
