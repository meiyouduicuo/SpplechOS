import Testing
import SwiftUI
@testable import ShellUI
#if os(macOS)
import AppKit

struct ConsoleThemeTests {
    @MainActor @Test func neutralSurfacesAndTextFollowBothAppearances() throws {
        for (name, light) in [(NSAppearance.Name.aqua, true), (.darkAqua, false)] {
            let appearance = try #require(NSAppearance(named: name))
            var background: NSColor?
            var ink: NSColor?
            appearance.performAsCurrentDrawingAppearance {
                background = NSColor(ShellPalette.background).usingColorSpace(.sRGB)
                ink = NSColor(ShellPalette.ink).usingColorSpace(.sRGB)
            }
            let bg = try #require(background), text = try #require(ink)
            #expect(abs(bg.redComponent - bg.blueComponent) < 0.04)
            #expect(light ? bg.redComponent > 0.9 : bg.redComponent < 0.2)
            #expect(abs(text.redComponent - bg.redComponent) > 0.7)
        }
    }
}
#endif
