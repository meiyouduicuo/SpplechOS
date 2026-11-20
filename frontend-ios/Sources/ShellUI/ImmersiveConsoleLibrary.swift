import SwiftUI

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
                            .foregroundStyle(.white.opacity(0.8))
                        Spacer()
                        if !nativeBars {
                            ControllerChip(count: controllers, action: openControllers)
                            ShellSettingsChip(action: openShellSettings)
                        }
                    }
                    .padding(.horizontal, margin)
                    .padding(.top, 12)
                }

                Spacer(minLength: landscape ? 8 : max(40, size.height * 0.16))

                HeroText(status: selected.game.state, title: selected.game.title,
                         explanation: selected.game.state == .playable ? "" : selected.game.state.explanation,
                         titleSize: compactLandscape ? 26 : landscape ? 36 : 38,
                         recentlyPlayed: selected.game.recentlyPlayed ?? "")
                    .frame(maxWidth: landscape ? size.width * 0.7 : .infinity, alignment: .leading)
                    .padding(.horizontal, margin)
                    .shadow(color: .black.opacity(0.55), radius: 12, y: 3)

                if !compactLandscape {
                    HStack {
                        Text(ShellStrings.text("Your games")).font(.headline)
                        Spacer()
                        Text("\(games.count)").monospacedDigit().foregroundStyle(.white.opacity(0.7))
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
                                    .background(.white.opacity(0.09), in: RoundedRectangle(cornerRadius: 12))
                                    .overlay { RoundedRectangle(cornerRadius: 12).strokeBorder(.white.opacity(0.25)) }
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
        .ignoresSafeArea(.container, edges: [.leading, .trailing])
        .accessibilityIdentifier("library.grid")
        .safeAreaInset(edge: .bottom, spacing: 0) {
            GameLaunchActions(game: selected.game, primary: { primary(selected) }, settings: openSettings,
                              expands: !landscape)
                .padding(.horizontal, margin).padding(.vertical, 14)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(.black.opacity(0.32))
                .hiddenIfObscured(obscured)
        }
    }

    private func tile(_ detail: GameDetail) -> some View {
        let chosen = selected.id == detail.id
        let focused = focus.visible && focus.id == "lib.tile.\(detail.id)"
        return Button { select(detail.id) } label: {
            VStack(alignment: .leading, spacing: 10) {
                CoverView(game: detail.game, showsState: true)
                    .overlay {
                        RoundedRectangle(cornerRadius: 10)
                            .strokeBorder(Color.cyan.opacity(chosen || focused ? 1 : 0.18), lineWidth: chosen || focused ? 3 : 1)
                    }
                    .shadow(color: .black.opacity(0.3), radius: 8, y: 4)
                    .shellTarget("lib.tile.\(detail.id)", showsRing: false) { primary(detail) }
                Text(detail.game.title).font(.subheadline.weight(chosen ? .semibold : .regular))
                    .lineLimit(typeSize.isAccessibilitySize ? 3 : 2)
                    .foregroundStyle(.white.opacity(chosen ? 1 : 0.75))
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

/// Keep artwork crisp. A quiet scenic wallpaper fills absent banners, including an empty library.
struct ConsoleBackdrop: View {
    var game: GameTile?
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                Image("ConsoleMountains", bundle: .module).resizable().scaledToFill()
                if let game, game.banner != nil {
                    ArtView(game: game, lettering: false)
                }
            }
            .frame(width: geometry.size.width, height: geometry.size.height).clipped()
            .overlay {
                LinearGradient(colors: [.black.opacity(0.12), .black.opacity(0.2), .black.opacity(0.78)],
                               startPoint: .top, endPoint: .bottom)
            }
        }.ignoresSafeArea().accessibilityHidden(true)
    }
}
