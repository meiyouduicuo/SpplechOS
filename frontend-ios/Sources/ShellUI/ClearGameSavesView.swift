import SwiftUI

/// Uses the library's existing destructive-action focus layer and starts on Cancel.
struct ClearGameSavesView: View {
    let game: GameTile
    let clear: () -> Void
    let cancel: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text(ShellStrings.text("Clear saves for “\(game.title)”?"))
                .shellType(ShellType.pageTitle)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
                .accessibilityIdentifier("clearSaves.title")
            Text(ShellStrings.text("Removes all current save slots for this game on this device. Your next launch starts a new game. Existing local backups remain available."))
                .shellText(15).foregroundStyle(.white.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)
            Text(ShellStrings.text("Cloud save sync for this game will be turned off. You can enable it again in Game settings."))
                .shellText(15).foregroundStyle(.white.opacity(0.78))
                .fixedSize(horizontal: false, vertical: true)
            Button(role: .destructive, action: clear) {
                Text(ShellStrings.text("Clear saves")).frame(maxWidth: .infinity)
            }
            .buttonStyle(.glassProminent).tint(DeleteStyle.red).controlSize(.large)
            .accessibilityIdentifier("clearSaves.confirm")
            .shellTarget("del.confirm", radius: 25, action: clear)
            Button(action: cancel) {
                Text(ShellStrings.text("Cancel")).frame(maxWidth: .infinity)
            }
            .buttonStyle(.glass).controlSize(.large)
            .accessibilityIdentifier("clearSaves.cancel")
            .shellTarget("del.cancel", action: cancel)
        }
        .padding(28)
        .frame(maxWidth: .infinity, alignment: .leading)
        .foregroundStyle(.white)
    }
}

private struct ShellAskClearSavesKey: EnvironmentKey {
    nonisolated(unsafe) static let defaultValue: ((GameTile) -> Void)? = nil
}

extension EnvironmentValues {
    var shellAskClearSaves: ((GameTile) -> Void)? {
        get { self[ShellAskClearSavesKey.self] }
        set { self[ShellAskClearSavesKey.self] = newValue }
    }
}
