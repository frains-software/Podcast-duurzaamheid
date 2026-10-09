import SwiftUI

struct HomeView: View {
    @Environment(EpisodeStore.self) private var store
    @Environment(AudioPlayer.self) private var player
    @State private var showPlayer = false
    @State private var showPublish = false
    @State private var showSettings = false
    @State private var appeared = false

    var body: some View {
        NavigationStack {
            ZStack {
                AuroraBackground(energy: player.isPlaying ? player.level() * 0.6 : 0, isActive: player.isPlaying)
                ScrollView {
                    VStack(alignment: .leading, spacing: 22) {
                        header
                        if let latest = store.latest {
                            TodayCard(episode: latest, onPlay: { play(latest) })
                                .offset(y: appeared ? 0 : 30)
                                .opacity(appeared ? 1 : 0)
                        } else if store.isLoading {
                            ProgressView().tint(.cream).frame(maxWidth: .infinity, minHeight: 240)
                        } else {
                            emptyState
                        }
                        if let next = store.nextReleaseDate() {
                            CountdownPill(target: next)
                        }
                        if !store.archive.isEmpty {
                            Eyebrow(text: "Eerdere afleveringen").padding(.top, 6)
                            VStack(spacing: 10) {
                                ForEach(store.archive) { episode in
                                    Button { play(episode) } label: { EpisodeRow(episode: episode) }
                                        .buttonStyle(.plain)
                                }
                            }
                        }
                        footer
                    }
                    .padding(.horizontal, 20)
                    .padding(.bottom, player.episode == nil ? 30 : 110)
                }
                .scrollIndicators(.hidden)
                .refreshable { await store.refresh() }
            }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: 4) {
                        Button { showPublish = true } label: {
                            Image(systemName: "dot.radiowaves.left.and.right")
                        }
                        .accessibilityLabel("Publiceren op Spotify")
                        Button { showSettings = true } label: {
                            Image(systemName: "slider.horizontal.3")
                        }
                        .accessibilityLabel("Instellingen")
                    }
                    .foregroundStyle(Color.cream)
                }
            }
            .toolbarBackground(.hidden, for: .navigationBar)
            .safeAreaInset(edge: .bottom) {
                if player.episode != nil {
                    MiniPlayer { showPlayer = true }
                        .padding(.horizontal, 12)
                        .padding(.bottom, 6)
                        .transition(.move(edge: .bottom).combined(with: .opacity))
                }
            }
            .animation(.spring(response: 0.45, dampingFraction: 0.85), value: player.episode?.id)
        }
        .fullScreenCover(isPresented: $showPlayer) { PlayerView() }
        .sheet(isPresented: $showPublish) { PublishView() }
        .sheet(isPresented: $showSettings) { SettingsView() }
        .onAppear {
            withAnimation(.spring(response: 0.7, dampingFraction: 0.8).delay(0.1)) { appeared = true }
        }
        .onOpenURL { url in
            if url.host() == "play", let latest = store.latest { play(latest) }
        }
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 12) {
            Image("Kringloop")
                .resizable()
                .frame(width: 46, height: 46)
                .rotationEffect(.degrees(appeared ? 0 : -120))
            VStack(alignment: .leading, spacing: 0) {
                Text("Grondstof")
                    .font(Theme.display(34))
                    .foregroundStyle(Color.cream)
                Text(store.show?.tagline ?? "Dagelijks stof tot nadenken")
                    .font(.subheadline)
                    .foregroundStyle(Color.cream.opacity(0.7))
            }
        }
        .padding(.top, 4)
    }

    private var emptyState: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow(text: "Bijna in de lucht")
                Text("De eerste aflevering komt eraan")
                    .font(Theme.display(24))
                    .foregroundStyle(Color.cream)
                Text(store.errorMessage ?? "Elke ochtend om negen uur verschijnt hier vijf minuten nieuws over duurzaamheid en circulaire economie.")
                    .foregroundStyle(Color.cream.opacity(0.75))
                Button("Opnieuw proberen") { Task { await store.refresh() } }
                    .buttonStyle(.borderedProminent)
                    .tint(.ember)
                    .padding(.top, 4)
            }
        }
    }

    private var footer: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Gepresenteerd door \(store.show?.host ?? "Frans van den Berge"), \(store.show?.hostRole ?? "namens De Graaf Groep").")
            Text((store.show?.companies ?? ["De Graaf Groep", "Wastenet", "Circular&Co.", "Product for Product"]).joined(separator: "  ·  "))
                .foregroundStyle(Color.amber.opacity(0.9))
        }
        .font(.footnote)
        .foregroundStyle(Color.cream.opacity(0.6))
        .padding(.top, 18)
    }

    private func play(_ episode: EpisodeSummary) {
        Task {
            await player.play(episode, store: store)
            showPlayer = true
        }
    }
}

/// Grote kaart met de nieuwste aflevering.
struct TodayCard: View {
    let episode: EpisodeSummary
    let onPlay: () -> Void
    @Environment(AudioPlayer.self) private var player

    var body: some View {
        GlassCard(padding: 22) {
            VStack(alignment: .leading, spacing: 14) {
                HStack {
                    Eyebrow(text: episode.isToday ? "Vandaag" : "Nieuwste aflevering")
                    Spacer()
                    Text(Formatting.longDay.string(from: episode.day))
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Color.cream.opacity(0.65))
                }
                Text(episode.title)
                    .font(Theme.display(28))
                    .foregroundStyle(Color.cream)
                    .fixedSize(horizontal: false, vertical: true)
                VStack(alignment: .leading, spacing: 9) {
                    ForEach(Array(episode.headlines.enumerated()), id: \.offset) { index, headline in
                        HStack(alignment: .firstTextBaseline, spacing: 10) {
                            Text("\(index + 1)")
                                .font(.caption.weight(.bold).monospacedDigit())
                                .foregroundStyle(Color.night)
                                .frame(width: 20, height: 20)
                                .background(Theme.fire, in: Circle())
                            Text(headline)
                                .font(.subheadline)
                                .foregroundStyle(Color.cream.opacity(0.88))
                                .fixedSize(horizontal: false, vertical: true)
                        }
                    }
                }
                if let number = episode.numberOfTheDay {
                    NumberOfTheDayCard(number: number)
                }
                Button(action: onPlay) {
                    HStack(spacing: 10) {
                        Image(systemName: player.isCurrent(episode) && player.isPlaying ? "waveform" : "play.fill")
                            .symbolEffect(.variableColor.iterative.reversing, isActive: player.isCurrent(episode) && player.isPlaying)
                        Text(player.isCurrent(episode) ? "Verder luisteren" : "Luister · \(episode.minutes) min")
                            .fontWeight(.semibold)
                    }
                    .font(.headline)
                    .foregroundStyle(Color.night)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 16)
                    .background(Theme.fire, in: Capsule())
                    .shadow(color: .ember.opacity(0.45), radius: 16, y: 6)
                }
                .buttonStyle(PressableStyle())
            }
        }
    }
}

struct EpisodeRow: View {
    let episode: EpisodeSummary
    @Environment(AudioPlayer.self) private var player

    var body: some View {
        HStack(spacing: 14) {
            VStack(spacing: 0) {
                Text("\(Calendar.current.component(.day, from: episode.day))")
                    .font(Theme.display(22))
                Text(Formatting.shortMonth.string(from: episode.day).replacingOccurrences(of: ".", with: "").uppercased())
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(Color.amber)
            }
            .frame(width: 52, height: 56)
            .background(Color.cream.opacity(0.08), in: RoundedRectangle(cornerRadius: 14, style: .continuous))

            VStack(alignment: .leading, spacing: 4) {
                Text(episode.title)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.cream)
                    .lineLimit(2)
                Text("Aflevering \(episode.number) · \(episode.minutes) min")
                    .font(.caption)
                    .foregroundStyle(Color.cream.opacity(0.6))
            }
            Spacer(minLength: 0)
            ProgressRing(progress: AudioPlayer.listenProgress(for: episode), isPlaying: player.isCurrent(episode) && player.isPlaying)
        }
        .padding(12)
        .background(.ultraThinMaterial.opacity(0.7), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .contentShape(Rectangle())
    }
}

struct ProgressRing: View {
    let progress: Double
    let isPlaying: Bool

    var body: some View {
        ZStack {
            Circle().stroke(Color.cream.opacity(0.15), lineWidth: 3)
            Circle()
                .trim(from: 0, to: progress)
                .stroke(Theme.fire, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                .rotationEffect(.degrees(-90))
            Image(systemName: progress >= 1 ? "checkmark" : (isPlaying ? "waveform" : "play.fill"))
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(Color.cream)
                .symbolEffect(.variableColor.iterative, isActive: isPlaying)
        }
        .frame(width: 36, height: 36)
    }
}

/// 'Nieuwe aflevering om 09:00 · nog 1 u 12 min'
struct CountdownPill: View {
    let target: Date

    var body: some View {
        TimelineView(.periodic(from: .now, by: 30)) { context in
            let minutes = max(0, Int(target.timeIntervalSince(context.date) / 60))
            HStack(spacing: 8) {
                Image(systemName: "clock.fill").foregroundStyle(Color.amber)
                Text("Nieuwe aflevering om \(target.formatted(date: .omitted, time: .shortened))")
                Spacer()
                Text(minutes >= 60 ? "nog \(minutes / 60) u \(minutes % 60) min" : "nog \(minutes) min")
                    .monospacedDigit()
                    .contentTransition(.numericText())
                    .foregroundStyle(Color.amber)
            }
            .font(.footnote.weight(.medium))
            .foregroundStyle(Color.cream)
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(.ultraThinMaterial.opacity(0.7), in: Capsule())
        }
    }
}

struct PressableStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.7), value: configuration.isPressed)
    }
}
