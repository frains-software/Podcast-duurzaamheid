import SwiftUI

/// De volledige speler: levende achtergrond, kringloop-visualisatie, golfvorm, bediening en meelezen.
struct PlayerView: View {
    @Environment(AudioPlayer.self) private var player
    @Environment(EpisodeStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var tab: Tab = .transcript

    enum Tab: String, CaseIterable, Identifiable {
        case transcript = "Meelezen"
        case chapters = "Hoofdstukken"
        case sources = "Bronnen"
        var id: String { rawValue }
    }

    var body: some View {
        ZStack {
            AuroraBackground(energy: player.isPlaying ? player.level() : 0, isActive: player.isPlaying)
            if let episode = player.episode {
                content(episode)
            }
        }
        .preferredColorScheme(.dark)
    }

    private func content(_ episode: EpisodeSummary) -> some View {
        VStack(spacing: 14) {
            topBar(episode)

            KringloopVisualizer(
                detail: player.detail,
                time: { player.estimatedTime(at: $0) },
                isPlaying: player.isPlaying,
                label: dayLabel(episode)
            )
            .frame(maxWidth: 300)
            .padding(.top, 2)

            VStack(spacing: 6) {
                Text(episode.title)
                    .font(Theme.display(22))
                    .multilineTextAlignment(.center)
                    .foregroundStyle(Color.cream)
                    .lineLimit(2)
                    .minimumScaleFactor(0.85)
                if let chapter = player.currentChapter {
                    HStack(spacing: 6) {
                        Image(systemName: chapter.symbol)
                        Text(chapter.kind == "story" ? chapter.title : chapter.kindLabel)
                            .lineLimit(1)
                    }
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.amber)
                    .id(chapter.index)
                    .transition(.asymmetric(insertion: .move(edge: .bottom).combined(with: .opacity), removal: .opacity))
                }
            }
            .animation(.smooth, value: player.currentChapter?.index)
            .padding(.horizontal, 24)

            WaveformScrubber(
                peaks: player.detail?.peaks ?? [],
                chapters: player.detail?.chapters ?? [],
                duration: player.duration,
                currentTime: player.currentTime,
                onSeek: { player.seek(to: $0) }
            )
            .padding(.horizontal, 24)

            controls
                .padding(.horizontal, 24)

            Picker("Weergave", selection: $tab) {
                ForEach(Tab.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .padding(.horizontal, 24)

            Group {
                if let detail = player.detail {
                    switch tab {
                    case .transcript:
                        TranscriptView(detail: detail, currentTime: player.currentTime) { player.seek(to: $0) }
                    case .chapters:
                        chapterList(detail)
                    case .sources:
                        sourceList(detail)
                    }
                } else {
                    ProgressView().tint(.cream).frame(maxHeight: .infinity)
                }
            }
            .padding(.horizontal, 24)
            .frame(maxHeight: .infinity)
        }
        .padding(.top, 8)
    }

    private func topBar(_ episode: EpisodeSummary) -> some View {
        HStack {
            Button { dismiss() } label: {
                Image(systemName: "chevron.down")
                    .font(.headline)
                    .frame(width: 40, height: 40)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel("Sluiten")
            Spacer()
            VStack(spacing: 2) {
                Eyebrow(text: "Aflevering \(episode.number)")
                Text(Formatting.longDay.string(from: episode.day).capitalized)
                    .font(.footnote)
                    .foregroundStyle(Color.cream.opacity(0.75))
            }
            Spacer()
            if let site = store.show?.websiteURL, let share = URL(string: site.absoluteString + "#\(episode.id)") {
                ShareLink(item: share, subject: Text("Grondstof"), message: Text(episode.title)) {
                    Image(systemName: "square.and.arrow.up")
                        .font(.headline)
                        .frame(width: 40, height: 40)
                        .background(.ultraThinMaterial, in: Circle())
                }
            } else {
                Color.clear.frame(width: 40, height: 40)
            }
        }
        .foregroundStyle(Color.cream)
        .padding(.horizontal, 20)
    }

    private var controls: some View {
        HStack {
            Button { player.nextRate() } label: {
                Text(rateLabel)
                    .font(.subheadline.weight(.semibold).monospacedDigit())
                    .frame(width: 54, height: 34)
                    .background(Color.cream.opacity(0.12), in: Capsule())
            }
            .accessibilityLabel("Afspeelsnelheid \(rateLabel)")
            Spacer()
            Button { player.skip(by: -15) } label: {
                Image(systemName: "gobackward.15").font(.title2)
            }
            .accessibilityLabel("15 seconden terug")
            Spacer()
            Button { player.toggle() } label: {
                ZStack {
                    Circle().fill(Theme.fire)
                        .shadow(color: .ember.opacity(0.6), radius: player.isPlaying ? 22 : 10)
                    Image(systemName: player.isPlaying ? "pause.fill" : "play.fill")
                        .font(.system(size: 30, weight: .bold))
                        .foregroundStyle(Color.night)
                        .contentTransition(.symbolEffect(.replace))
                        .offset(x: player.isPlaying ? 0 : 2)
                }
                .frame(width: 78, height: 78)
            }
            .accessibilityLabel(player.isPlaying ? "Pauzeer" : "Speel af")
            .sensoryFeedback(.impact(weight: .medium), trigger: player.isPlaying)
            Spacer()
            Button { player.skip(by: 15) } label: {
                Image(systemName: "goforward.15").font(.title2)
            }
            .accessibilityLabel("15 seconden vooruit")
            Spacer()
            Menu {
                ForEach(player.detail?.chapters ?? []) { chapter in
                    Button {
                        player.jump(to: chapter)
                    } label: {
                        Label("\(Formatting.clock(chapter.start))  \(chapter.title)", systemImage: chapter.symbol)
                    }
                }
            } label: {
                Image(systemName: "list.bullet")
                    .font(.headline)
                    .frame(width: 54, height: 34)
                    .background(Color.cream.opacity(0.12), in: Capsule())
            }
            .accessibilityLabel("Hoofdstukken")
        }
        .foregroundStyle(Color.cream)
    }

    private var rateLabel: String {
        var text = String(format: "%.2f", Double(player.rate))
        while text.hasSuffix("0") { text.removeLast() }
        if text.hasSuffix(".") { text.removeLast() }
        return text.replacingOccurrences(of: ".", with: ",") + "×"
    }

    private func dayLabel(_ episode: EpisodeSummary) -> String {
        let day = Calendar.current.component(.day, from: episode.day)
        return "\(day) \(Formatting.shortMonth.string(from: episode.day).replacingOccurrences(of: ".", with: ""))"
    }

    private func chapterList(_ detail: EpisodeDetail) -> some View {
        let active = detail.chapterIndex(at: player.currentTime)
        return ScrollView(showsIndicators: false) {
            VStack(spacing: 8) {
                ForEach(detail.chapters) { chapter in
                    Button { player.jump(to: chapter) } label: {
                        HStack(alignment: .top, spacing: 14) {
                            Text(Formatting.clock(chapter.start))
                                .font(.footnote.monospacedDigit().weight(.semibold))
                                .foregroundStyle(Color.amber)
                                .frame(width: 42, alignment: .leading)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(chapter.kindLabel.uppercased())
                                    .font(.caption2.weight(.semibold))
                                    .foregroundStyle(Color.cream.opacity(0.55))
                                Text(chapter.title)
                                    .font(.body.weight(.medium))
                                    .multilineTextAlignment(.leading)
                            }
                            Spacer(minLength: 0)
                            if chapter.index == active, player.isPlaying {
                                Image(systemName: "waveform")
                                    .symbolEffect(.variableColor.iterative.reversing, isActive: true)
                                    .foregroundStyle(Color.amber)
                            }
                        }
                        .padding(12)
                        .background(Color.cream.opacity(chapter.index == active ? 0.12 : 0.05), in: RoundedRectangle(cornerRadius: 16))
                    }
                    .foregroundStyle(Color.cream)
                }
            }
            .padding(.vertical, 12)
        }
    }

    private func sourceList(_ detail: EpisodeDetail) -> some View {
        ScrollView(showsIndicators: false) {
            VStack(alignment: .leading, spacing: 10) {
                if let number = detail.numberOfTheDay {
                    NumberOfTheDayCard(number: number)
                }
                ForEach(detail.sources) { source in
                    Button {
                        if let link = source.link { openURL(link) }
                    } label: {
                        HStack(spacing: 12) {
                            Image(systemName: "link")
                                .foregroundStyle(Color.amber)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(source.displayPublisher)
                                    .font(.caption.weight(.semibold))
                                    .foregroundStyle(Color.amber)
                                Text(source.title ?? source.url)
                                    .font(.subheadline)
                                    .multilineTextAlignment(.leading)
                                    .lineLimit(2)
                            }
                            Spacer(minLength: 0)
                            Image(systemName: "arrow.up.right").font(.caption)
                        }
                        .padding(12)
                        .background(Color.cream.opacity(0.06), in: RoundedRectangle(cornerRadius: 16))
                    }
                    .foregroundStyle(Color.cream)
                }
            }
            .padding(.vertical, 12)
        }
    }
}

/// 'Het cijfer van de dag' als grote, warme kaart.
struct NumberOfTheDayCard: View {
    let number: NumberOfTheDay
    @State private var appeared = false

    var body: some View {
        HStack(alignment: .center, spacing: 16) {
            Text(number.value)
                .font(Theme.display(40))
                .foregroundStyle(Theme.fire)
                .minimumScaleFactor(0.6)
                .lineLimit(1)
                .scaleEffect(appeared ? 1 : 0.6)
                .opacity(appeared ? 1 : 0)
            VStack(alignment: .leading, spacing: 4) {
                Eyebrow(text: "Cijfer van de dag")
                Text(number.label)
                    .font(.subheadline)
                    .foregroundStyle(Color.cream.opacity(0.85))
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.night.opacity(0.35), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Theme.fire.opacity(0.5), lineWidth: 1))
        .onAppear {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.65).delay(0.15)) { appeared = true }
        }
    }
}
