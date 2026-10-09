import AVFoundation
import MediaPlayer
import Observation
import UIKit

/// Speler met achtergrondaudio, vergrendelscherm-bediening, hervatpunten en afspeelsnelheid.
@Observable
final class AudioPlayer {
    private(set) var episode: EpisodeSummary?
    private(set) var detail: EpisodeDetail?
    private(set) var isPlaying = false
    private(set) var isBuffering = false
    private(set) var currentTime: Double = 0
    private(set) var duration: Double = 0
    var rate: Float = UserDefaults.standard.object(forKey: "rate") as? Float ?? 1.0 {
        didSet {
            UserDefaults.standard.set(rate, forKey: "rate")
            player.defaultRate = rate
            if isPlaying { player.rate = rate }
            updateNowPlaying()
        }
    }

    static let rates: [Float] = [1.0, 1.15, 1.3, 1.5, 0.85]

    @ObservationIgnored private let player = AVPlayer()
    @ObservationIgnored private var timeObserver: Any?
    @ObservationIgnored private var statusObservation: NSKeyValueObservation?
    @ObservationIgnored private var endObserver: NSObjectProtocol?
    @ObservationIgnored private var artwork: MPMediaItemArtwork?
    @ObservationIgnored private var lastTick = Date()

    init() {
        player.defaultRate = rate
        player.automaticallyWaitsToMinimizeStalling = true
        if let image = UIImage(named: "Cover") {
            artwork = MPMediaItemArtwork(boundsSize: image.size) { _ in image }
        }
        timeObserver = player.addPeriodicTimeObserver(
            forInterval: CMTime(seconds: 0.1, preferredTimescale: 600), queue: .main
        ) { [weak self] time in
            self?.tick(time.seconds)
        }
        statusObservation = player.observe(\.timeControlStatus, options: [.initial, .new]) { [weak self] player, _ in
            let status = player.timeControlStatus
            DispatchQueue.main.async {
                self?.isPlaying = status != .paused
                self?.isBuffering = status == .waitingToPlayAtSpecifiedRate
                self?.updateNowPlaying()
            }
        }
        configureRemoteCommands()
    }

    // MARK: - Afspelen

    var currentChapter: Chapter? {
        guard let detail, !detail.chapters.isEmpty else { return nil }
        return detail.chapters[detail.chapterIndex(at: currentTime)]
    }

    var progress: Double { duration > 0 ? min(1, currentTime / duration) : 0 }

    func isCurrent(_ episode: EpisodeSummary) -> Bool { self.episode?.id == episode.id }

    @MainActor
    func play(_ episode: EpisodeSummary, store: EpisodeStore) async {
        if isCurrent(episode) {
            if !isPlaying { resume() }
            return
        }
        guard let url = episode.audioURL else { return }
        savePosition()
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, policy: .longFormAudio)
        try? AVAudioSession.sharedInstance().setActive(true)

        self.episode = episode
        self.detail = nil
        self.duration = episode.duration
        let item = AVPlayerItem(url: url)
        item.audioTimePitchAlgorithm = .timeDomain
        observeEnd(of: item)
        player.replaceCurrentItem(with: item)

        let saved = UserDefaults.standard.double(forKey: Self.positionKey(episode.id))
        let start = saved > 5 && saved < episode.duration - 10 ? saved : 0
        currentTime = start
        if start > 0 {
            _ = await player.seek(to: CMTime(seconds: start, preferredTimescale: 600))
        }
        resume()
        updateNowPlaying()
        detail = await store.detail(for: episode)
    }

    func toggle() {
        isPlaying ? pause() : resume()
    }

    func resume() {
        guard player.currentItem != nil else { return }
        if duration > 0, currentTime >= duration - 0.5 { seek(to: 0) }
        player.playImmediately(atRate: rate)
    }

    func pause() {
        player.pause()
        savePosition()
    }

    func seek(to seconds: Double) {
        let target = max(0, min(seconds, max(duration - 0.2, 0)))
        currentTime = target
        player.seek(to: CMTime(seconds: target, preferredTimescale: 600), toleranceBefore: .zero, toleranceAfter: .zero)
        updateNowPlaying()
    }

    func skip(by seconds: Double) { seek(to: currentTime + seconds) }

    func jump(to chapter: Chapter) {
        seek(to: chapter.start)
        if !isPlaying { resume() }
    }

    func nextRate() {
        let i = Self.rates.firstIndex(of: rate) ?? 0
        rate = Self.rates[(i + 1) % Self.rates.count]
    }

    /// Positie geëxtrapoleerd naar `date`, voor animaties die vaker verversen dan de tijdsupdates.
    func estimatedTime(at date: Date) -> Double {
        guard isPlaying, !isBuffering else { return currentTime }
        let elapsed = min(0.5, max(0, date.timeIntervalSince(lastTick)))
        return currentTime + elapsed * Double(rate)
    }

    /// Energie op dit moment (0…1) voor de animaties, afgeleid van de vooraf berekende golfvorm.
    func level(at time: Double? = nil) -> Double {
        guard let detail else { return 0 }
        return detail.level(at: time ?? currentTime)
    }

    // MARK: - Luistergeschiedenis

    static func positionKey(_ id: String) -> String { "position-\(id)" }
    static func finishedKey(_ id: String) -> String { "finished-\(id)" }

    static func listenProgress(for episode: EpisodeSummary) -> Double {
        if UserDefaults.standard.bool(forKey: finishedKey(episode.id)) { return 1 }
        let pos = UserDefaults.standard.double(forKey: positionKey(episode.id))
        return episode.duration > 0 ? min(1, pos / episode.duration) : 0
    }

    private func savePosition() {
        guard let id = episode?.id, currentTime > 0 else { return }
        UserDefaults.standard.set(currentTime, forKey: Self.positionKey(id))
    }

    // MARK: - Intern

    private func tick(_ seconds: Double) {
        guard seconds.isFinite else { return }
        currentTime = seconds
        lastTick = Date()
        if let d = player.currentItem?.duration.seconds, d.isFinite, d > 0 { duration = d }
        if Int(seconds * 10) % 50 == 0 { savePosition() }
    }

    private func observeEnd(of item: AVPlayerItem) {
        if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
        endObserver = NotificationCenter.default.addObserver(
            forName: AVPlayerItem.didPlayToEndTimeNotification, object: item, queue: .main
        ) { [weak self] _ in
            guard let self, let id = self.episode?.id else { return }
            UserDefaults.standard.set(true, forKey: Self.finishedKey(id))
            UserDefaults.standard.removeObject(forKey: Self.positionKey(id))
            self.isPlaying = false
        }
    }

    private func configureRemoteCommands() {
        let center = MPRemoteCommandCenter.shared()
        center.playCommand.addTarget { [weak self] _ in self?.resume(); return .success }
        center.pauseCommand.addTarget { [weak self] _ in self?.pause(); return .success }
        center.togglePlayPauseCommand.addTarget { [weak self] _ in self?.toggle(); return .success }
        center.skipForwardCommand.preferredIntervals = [15]
        center.skipBackwardCommand.preferredIntervals = [15]
        center.skipForwardCommand.addTarget { [weak self] _ in self?.skip(by: 15); return .success }
        center.skipBackwardCommand.addTarget { [weak self] _ in self?.skip(by: -15); return .success }
        center.changePlaybackPositionCommand.addTarget { [weak self] event in
            guard let event = event as? MPChangePlaybackPositionCommandEvent else { return .commandFailed }
            self?.seek(to: event.positionTime)
            return .success
        }
    }

    private func updateNowPlaying() {
        guard let episode else { return }
        var info: [String: Any] = [
            MPMediaItemPropertyTitle: episode.title,
            MPMediaItemPropertyArtist: "Grondstof · Frans van den Berge",
            MPMediaItemPropertyAlbumTitle: "Grondstof",
            MPMediaItemPropertyPlaybackDuration: duration,
            MPNowPlayingInfoPropertyElapsedPlaybackTime: currentTime,
            MPNowPlayingInfoPropertyPlaybackRate: isPlaying ? Double(rate) : 0.0,
            MPNowPlayingInfoPropertyDefaultPlaybackRate: Double(rate),
            MPNowPlayingInfoPropertyMediaType: MPNowPlayingInfoMediaType.audio.rawValue,
        ]
        if let artwork { info[MPMediaItemPropertyArtwork] = artwork }
        MPNowPlayingInfoCenter.default().nowPlayingInfo = info
    }
}
