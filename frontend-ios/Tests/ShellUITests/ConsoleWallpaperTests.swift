import Testing
@testable import ShellUI

struct ConsoleWallpaperTests {
    @Test func bundledWallpaperDecodesAtFullResolution() throws {
        let wallpaper = try #require(ConsoleWallpaper.artwork)
        #expect(wallpaper.image.width >= 1600)
        #expect(wallpaper.image.height >= 900)
        #expect(wallpaper.tone.blue > 0.05)
    }
}
