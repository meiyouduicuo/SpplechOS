import SwiftUI
#if canImport(UIKit)
import UIKit
#endif

struct PeerGameTransferView: View {
    @Bindable var transfer: PeerGameTransfer
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        NavigationStack {
            List {
                Section {
                    Text(hostText("Keep both devices nearby with Wi-Fi on and both apps open."))
                    Text(hostText("Only the game's framework, artwork and data are transferred. Saves are never sent or cleared."))
                        .font(.footnote).foregroundStyle(.secondary)
                }
                switch transfer.phase {
                case .searching:
                    Section {
                        ProgressView(transfer.sending ? hostText("Searching for receiving devices…") : hostText("Waiting for another device…"))
                        Text(transfer.sending ? hostText("On the other device, open App settings and choose Receive a game.") : hostText("On the sending device, open Game settings and choose Send to another device."))
                            .font(.footnote)
                        ForEach(transfer.devices) { device in
                            Button(device.name) { transfer.choose(device) }
                        }
                    }
                case .waiting:
                    ProgressView(hostText("Waiting for the other device to accept…"))
                case .connecting, .preparing:
                    ProgressView(transfer.phase == .connecting ? hostText("Checking connection and signing compatibility…") : hostText("Preparing game files without making a copy…"))
                case .pairing:
                    Section {
                        Text(hostText("Check that both devices show the same code."))
                        Text(transfer.code).font(.system(.largeTitle, design: .monospaced).bold())
                            .accessibilityIdentifier("peer.code")
                        if !transfer.peerName.isEmpty { Text(transfer.peerName).foregroundStyle(.secondary) }
                        Button(hostText("Codes match — continue")) { transfer.confirm() }
                            .accessibilityIdentifier("peer.confirmCode")
                    }
                case .offer:
                    Section {
                        Text(transfer.gameTitle).font(.headline)
                        Text(ByteCountFormatter.string(fromByteCount: Int64(transfer.offeredBytes), countStyle: .file))
                        Text(hostText("An existing copy of this game will be updated after verification. Its saves and settings stay unchanged."))
                            .font(.footnote)
                        Button(hostText("Receive and import")) { transfer.confirm() }
                            .accessibilityIdentifier("peer.accept")
                    }
                case .transferring:
                    Section {
                        Text(transfer.gameTitle).font(.headline)
                        ProgressView(value: transfer.progress)
                            .accessibilityIdentifier("peer.progress")
                        Text(transfer.progress, format: .percent.precision(.fractionLength(0)))
                        Text(hostText("Keep this app open until the transfer finishes."))
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                case .complete:
                    Label(hostText("Game transfer complete."), systemImage: "checkmark.circle.fill")
                        .accessibilityIdentifier("peer.complete")
                case .failed:
                    Text(transfer.message).foregroundStyle(.red)
                    Text(hostText("Close this screen and try again. Allow local network access in Settings if needed."))
                        .font(.footnote)
                }
            }
            .navigationTitle(transfer.sending ? hostText("Send game") : hostText("Receive game"))
            #if os(iOS)
            .navigationBarTitleDisplayMode(.inline)
            #endif
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(transfer.phase == .complete || transfer.phase == .failed ? hostText("Close") : hostText("Cancel")) { transfer.stop(); dismiss() }
                        .accessibilityIdentifier("peer.close")
                }
            }
        }
        .interactiveDismissDisabled(transfer.phase == .transferring)
        .task { transfer.start() }
        .onDisappear { transfer.stop() }
        #if canImport(UIKit)
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didEnterBackgroundNotification)) { _ in
            transfer.stop()
            transfer.message = hostText("Transfer cancelled. Keep both apps open while transferring.")
            transfer.phase = .failed
        }
        #endif
    }
}
