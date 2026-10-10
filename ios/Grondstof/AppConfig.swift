import Foundation

enum AppConfig {
    /// Waar de studio de feed en `episodes.json` publiceert (GitHub Pages).
    static let defaultSiteURL = URL(string: "https://frains-software.github.io/Podcast-duurzaamheid")!

    /// Kan in Instellingen worden overschreven, handig bij een eigen domein.
    static var siteURL: URL {
        if let custom = UserDefaults.standard.string(forKey: "siteURL"),
           let url = URL(string: custom.trimmingCharacters(in: .whitespaces)),
           url.scheme == "https" || ["localhost", "127.0.0.1"].contains(url.host() ?? "") {
            return url
        }
        return defaultSiteURL
    }

    static var indexURL: URL { siteURL.appending(path: "episodes.json") }
    static var feedURL: URL { siteURL.appending(path: "feed.xml") }

    static let linkedIn = URL(string: "https://www.linkedin.com/in/fransvdberge/")!
    static let spotifyForCreators = URL(string: "https://creators.spotify.com/")!
    static let applePodcastsConnect = URL(string: "https://podcastsconnect.apple.com/")!

    static let reminderHour = 9
    static let reminderMinute = 5
}
