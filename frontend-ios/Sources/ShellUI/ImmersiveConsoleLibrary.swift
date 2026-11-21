import SwiftUI
import Foundation

/// Console-style selection with a single horizontal shelf, in either orientation.
/// The native toolbar retains app settings. The sliders below belong to the selected game.
struct ImmersiveConsoleLibrary: View {
    let games: [GameDetail]
    let selected: GameDetail
    let size: CGSize
    let obscured: Bool
    let controllers: Int
    let select: (String) -> Void
    let primary: (GameDetail) -> Void
    let openSettings: () -> Void
    let openControllers: () -> Void
    let openShellSettings: () -> Void
    let importPackage: () -> Void
    @Environment(\.shellNativeBars) private var nativeBars
    @Environment(\.shellFocus) private var focus
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.dynamicTypeSize) private var typeSize

    private var landscape: Bool { size.width > size.height }
    private var compactLandscape: Bool { landscape && size.height < 440 }
    private var margin: CGFloat { landscape && !compactLandscape ? 32 : 24 }
    private var cardWidth: CGFloat {
        min(typeSize.isAccessibilitySize ? 320 : compactLandscape ? 176 : landscape ? 220 : 264, max(140, size.width * 0.62))
    }

    var body: some View {
        ScrollView(.vertical) {
            VStack(alignment: .leading, spacing: compactLandscape ? 12 : landscape ? 18 : 28) {
                if !compactLandscape || !nativeBars {
                    HStack {
                        Text("SpplechOS").font(.headline).tracking(2)
                            .foregroundStyle(.secondary)
                        Spacer()
                        if !nativeBars {
                            ControllerChip(count: controllers, action: openControllers)
                            ShellSettingsChip(action: openShellSettings)
                        }
                    }
                    .padding(.horizontal, margin)
                    .padding(.top, 12)
                }

                Spacer(minLength: landscape ? 8 : 24)

                VStack(alignment: .leading, spacing: 8) {
                    if let played = selected.game.recentlyPlayed {
                        Text(played).font(.subheadline).foregroundStyle(.secondary)
                    }
                    Text(selected.game.title)
                        .shellType(ShellType.heroTitle(compactLandscape ? 26 : 34))
                        .lineLimit(2).accessibilityAddTraits(.isHeader)
                        .accessibilityIdentifier("hero.title")
                    if selected.game.state != .playable { StatusLabel(state: selected.game.state) }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, margin)

                if !compactLandscape {
                    HStack {
                        Text(ShellStrings.text("Your games")).font(.headline)
                        Spacer()
                        Text("\(games.count)").monospacedDigit().foregroundStyle(.secondary)
                    }.padding(.horizontal, margin)
                }

                ScrollViewReader { proxy in
                    ScrollView(.horizontal) {
                        LazyHStack(alignment: .top, spacing: 18) {
                            ForEach(games) { detail in tile(detail) }
                            Button(action: importPackage) {
                                Image(systemName: "plus")
                                    .font(.system(size: 32, weight: .light))
                                    .frame(width: 92, height: cardWidth * 9 / 16)
                                    .background(ShellPalette.surface, in: RoundedRectangle(cornerRadius: 12))
                                    .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(ShellPalette.hairline) }
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel(ShellStrings.text("Import game package…"))
                            .accessibilityIdentifier("console.import")
                            .shellTarget("lib.packageTile", action: importPackage)
                        }.padding(.horizontal, margin).padding(.vertical, 6)
                    }
                    .scrollIndicators(.hidden)
                    .onChange(of: selected.id) { _, id in
                        withAnimation(reduceMotion ? nil : .easeOut(duration: 0.2)) { proxy.scrollTo(id, anchor: .center) }
                    }
                    .onChange(of: focus.id) { _, id in
                        guard let id, id.hasPrefix("lib.tile.") else { return }
                        withAnimation(reduceMotion ? nil : .easeOut(duration: 0.2)) {
                            proxy.scrollTo(String(id.dropFirst("lib.tile.".count)), anchor: .center)
                        }
                    }
                }
            }
            .frame(minHeight: max(0, size.height - 100), alignment: .top)
            .padding(.bottom, 12)
        }
        .scrollIndicators(.hidden)
        .scrollContentBackground(.hidden)
        .ignoresSafeArea(.container, edges: [.leading, .trailing])
        .accessibilityIdentifier("library.grid")
        .safeAreaInset(edge: .bottom, spacing: 0) {
            GameLaunchActions(game: selected.game, primary: { primary(selected) }, settings: openSettings,
                              expands: !landscape, primaryTint: ShellPalette.action, primaryInk: .white)
                .padding(.horizontal, margin).padding(.vertical, 14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(ShellPalette.background)
                .overlay(alignment: .top) { Rectangle().fill(ShellPalette.hairline).frame(height: 1) }
                .hiddenIfObscured(obscured)
        }
    }

    private func tile(_ detail: GameDetail) -> some View {
        let chosen = selected.id == detail.id
        let focused = focus.visible && focus.id == "lib.tile.\(detail.id)"
        return Button { select(detail.id) } label: {
            VStack(alignment: .leading, spacing: 10) {
                CoverView(game: detail.game, showsState: true)
                    .frame(width: cardWidth, height: cardWidth * 9 / 16)
                    .overlay {
                        RoundedRectangle(cornerRadius: 10)
                            .strokeBorder(ShellPalette.accent.opacity(chosen || focused ? 1 : 0.18), lineWidth: chosen || focused ? 3 : 1)
                    }
                    .shadow(color: .black.opacity(0.3), radius: 8, y: 4)
                    .shellTarget("lib.tile.\(detail.id)", showsRing: false) { primary(detail) }
                Text(detail.game.title).font(.subheadline.weight(chosen ? .semibold : .regular))
                    .lineLimit(typeSize.isAccessibilitySize ? 3 : 2)
                    .foregroundStyle(ShellPalette.ink.opacity(chosen ? 1 : 0.7))
            }.frame(width: cardWidth).contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(detail.game.title + ", " + detail.game.state.title)
        .accessibilityAddTraits(chosen ? .isSelected : [])
        .accessibilityIdentifier("tile.\(detail.id)")
        .accessibilityAction(named: Text(ShellStrings.text("Game settings"))) { select(detail.id); openSettings() }
        .contextMenu {
            Button(ShellStrings.text("Play"), systemImage: "play.fill") { primary(detail) }
                .disabled(detail.game.state != .playable)
            Button(ShellStrings.text("Game settings"), systemImage: "slider.horizontal.3") { select(detail.id); openSettings() }
        }
        .id(detail.id)
    }
}

private extension View {
    @ViewBuilder func hiddenIfObscured(_ obscured: Bool) -> some View {
        if obscured { hidden() } else { self }
    }
}

/// A neutral console surface follows the system appearance, independent of game artwork.
struct ConsoleBackdrop: View {
    var body: some View {
        ShellPalette.background.ignoresSafeArea().accessibilityHidden(true)
    }
}
