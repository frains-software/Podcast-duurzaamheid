import Foundation
import Observation

/// Haalt de afleveringen op en bewaart ze lokaal, zodat de app ook offline opent.
@MainActor
@Observable
final class EpisodeStore {
    private(set) var show: ShowInfo?
    private(set) var episodes: [EpisodeSummary] = []
    private(set) var isLoading = false
    private(set) var errorMessage: String?
    private(set) var lastUpdated: Date?
    private var details: [String: EpisodeDetail] = [:]

    private let decoder = JSONDecoder()
    private let session: URLSession = {
        let config = URLSessionConfiguration.default
        config.requestCachePolicy = .reloadRevalidatingCacheData
        config.timeoutIntervalForRequest = 20
        return URLSession(configuration: config)
    }()

    init() {
        if let data = try? Data(contentsOf: Self.cacheFile("episodes.json")),
           let index = try? decoder.decode(EpisodeIndex.self, from: data) {
            apply(index)
        }
    }

    var latest: EpisodeSummary? { episodes.first }
    var archive: [EpisodeSummary] { Array(episodes.dropFirst()) }

    func refresh() async {
        guard !isLoading else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let (data, response) = try await session.data(from: AppConfig.indexURL)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                throw URLError(.badServerResponse)
            }
            let index = try decoder.decode(EpisodeIndex.self, from: data)
            apply(index)
            errorMessage = nil
            try? data.write(to: Self.cacheFile("episodes.json"), options: .atomic)
        } catch {
            errorMessage = episodes.isEmpty
                ? "Nog geen afleveringen gevonden. Controleer je verbinding of probeer het straks opnieuw."
                : nil
        }
    }

    func detail(for episode: EpisodeSummary) async -> EpisodeDetail? {
        if let cached = details[episode.id] { return cached }
        let file = Self.cacheFile("episode-\(episode.id).json")
        if let data = try? Data(contentsOf: file), let detail = try? decoder.decode(EpisodeDetail.self, from: data) {
            details[episode.id] = detail
            return detail
        }
        guard let url = episode.detailURL else { return nil }
        do {
            let (data, _) = try await session.data(from: url)
            let detail = try decoder.decode(EpisodeDetail.self, from: data)
            details[episode.id] = detail
            try? data.write(to: file, options: .atomic)
            return detail
        } catch {
            return nil
        }
    }

    /// Minuten tot de volgende aflevering, als die van vandaag nog niet uit is.
    func nextReleaseDate(now: Date = .now) -> Date? {
        if latest?.isToday == true { return nil }
        let parts = (show?.publishTime ?? "09:00").split(separator: ":").compactMap { Int($0) }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: show?.timezone ?? "Europe/Amsterdam") ?? .current
        var comps = calendar.dateComponents([.year, .month, .day], from: now)
        comps.hour = parts.first ?? 9
        comps.minute = parts.count > 1 ? parts[1] : 0
        guard let today = calendar.date(from: comps) else { return nil }
        return today > now ? today : nil
    }

    private func apply(_ index: EpisodeIndex) {
        show = index.show
        episodes = index.episodes.sorted { $0.date > $1.date }
        lastUpdated = .now
    }

    private static func cacheFile(_ name: String) -> URL {
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        return dir.appending(path: name)
    }
}
