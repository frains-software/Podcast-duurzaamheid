import Foundation

/// Spiegelt `episodes.json` en `episodes/<id>.json` zoals de studio ze publiceert.
struct EpisodeIndex: Codable {
    let generated: String
    let show: ShowInfo
    let episodes: [EpisodeSummary]
}

struct ShowInfo: Codable, Hashable {
    let title: String
    let subtitle: String
    let tagline: String
    let description: String
    let host: String
    let hostRole: String
    let organisation: String
    let companies: [String]
    let cover: String
    let feedUrl: String
    let website: String
    let spotifyUrl: String?
    let appleUrl: String?
    let publishTime: String
    let timezone: String

    var feedURL: URL? { URL(string: feedUrl) }
    var websiteURL: URL? { URL(string: website) }
    var spotifyURL: URL? { spotifyUrl.flatMap(URL.init(string:)) }
    var appleURL: URL? { appleUrl.flatMap(URL.init(string:)) }
}

struct SourceLink: Codable, Hashable, Identifiable {
    let publisher: String?
    let title: String?
    let url: String

    var id: String { url }
    var link: URL? { URL(string: url) }
    var displayPublisher: String {
        if let publisher, !publisher.isEmpty { return publisher }
        return link?.host()?.replacingOccurrences(of: "www.", with: "") ?? "Bron"
    }
}

struct NumberOfTheDay: Codable, Hashable {
    let value: String
    let label: String
    let source: SourceLink?
}

struct EpisodeSummary: Codable, Hashable, Identifiable {
    let id: String
    let number: Int
    let date: String
    let published: String
    let title: String
    let summary: String
    let duration: Double
    let audioUrl: String
    let detailUrl: String
    let headlines: [String]
    let numberOfTheDay: NumberOfTheDay?

    var audioURL: URL? { URL(string: audioUrl) }
    var detailURL: URL? { URL(string: detailUrl) }
    var day: Date { Formatting.isoDay.date(from: date) ?? .distantPast }
    var isToday: Bool { Calendar.current.isDateInToday(day) }
    var minutes: Int { max(1, Int((duration / 60).rounded())) }
}

struct Chapter: Codable, Hashable, Identifiable {
    let index: Int
    let kind: String
    let kindLabel: String
    let title: String
    let start: Double
    let sources: [SourceLink]

    var id: Int { index }
    var symbol: String {
        switch kind {
        case "intro": return "sunrise.fill"
        case "story": return "newspaper.fill"
        case "insight": return "lightbulb.max.fill"
        case "number": return "number"
        default: return "moon.stars.fill"
        }
    }
}

struct Cue: Codable, Hashable {
    let start: Double
    let end: Double
    let text: String
    let chapter: Int
}

struct EpisodeDetail: Codable, Hashable {
    let id: String
    let number: Int
    let date: String
    let title: String
    let summary: String
    let duration: Double
    let audioUrl: String
    let numberOfTheDay: NumberOfTheDay?
    let chapters: [Chapter]
    let transcript: [Cue]
    let sources: [SourceLink]
    let peaksPerSecond: Int
    let peaks: [Double]

    func chapterIndex(at time: Double) -> Int {
        chapters.lastIndex { $0.start <= time + 0.05 } ?? 0
    }

    func cueIndex(at time: Double) -> Int? {
        transcript.lastIndex { $0.start <= time + 0.05 }
    }

    /// Geïnterpoleerde energie (0…1) op tijdstip `time`, voor de visualisaties.
    func level(at time: Double) -> Double {
        guard !peaks.isEmpty else { return 0 }
        let position = max(0, time) * Double(peaksPerSecond)
        let lower = min(Int(position), peaks.count - 1)
        let upper = min(lower + 1, peaks.count - 1)
        let fraction = position - Double(lower)
        return peaks[lower] * (1 - fraction) + peaks[upper] * fraction
    }

    /// Een venster van `count` waarden rond `time`, voor de ronde golfvorm.
    func window(around time: Double, count: Int, span: Double) -> [Double] {
        guard !peaks.isEmpty, count > 0 else { return Array(repeating: 0, count: max(count, 0)) }
        return (0..<count).map { i in
            let offset = (Double(i) / Double(count) - 0.5) * span
            return level(at: time + offset)
        }
    }
}

enum Formatting {
    static let isoDay: DateFormatter = {
        let f = DateFormatter()
        f.calendar = Calendar(identifier: .gregorian)
        f.locale = Locale(identifier: "en_US_POSIX")
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()

    static let longDay: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "nl_NL")
        f.dateFormat = "EEEE d MMMM"
        return f
    }()

    static let shortMonth: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "nl_NL")
        f.dateFormat = "MMM"
        return f
    }()

    /// "Vrijdag 9 oktober": alleen de eerste letter als hoofdletter.
    static func dayTitle(_ date: Date) -> String {
        let text = longDay.string(from: date)
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    static func clock(_ seconds: Double) -> String {
        guard seconds.isFinite else { return "0:00" }
        let s = max(0, Int(seconds.rounded(.down)))
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}
