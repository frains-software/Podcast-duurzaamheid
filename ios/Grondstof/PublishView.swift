import SwiftUI
import UIKit

/// Publiceren op Spotify (en Apple Podcasts). Spotify haalt de RSS-feed die de studio elke
/// ochtend bijwerkt zelf op: eenmalig aanmelden, daarna verschijnt elke aflevering vanzelf.
struct PublishView: View {
    @Environment(EpisodeStore.self) private var store
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    @State private var copied = false
    @State private var feedStatus: FeedStatus = .checking

    enum FeedStatus: Equatable {
        case checking, online(Int), offline
    }

    private var feed: URL { store.show?.feedURL ?? AppConfig.feedURL }

    var body: some View {
        NavigationStack {
            ZStack {
                AuroraBackground()
                ScrollView {
                    VStack(alignment: .leading, spacing: 18) {
                        hero
                        if let spotify = store.show?.spotifyURL {
                            liveCard(spotify)
                        }
                        feedCard
                        steps
                        appleCard
                    }
                    .padding(20)
                }
            }
            .navigationTitle("Publiceren")
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(.hidden, for: .navigationBar)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Klaar") { dismiss() }.foregroundStyle(Color.cream)
                }
            }
            .task { await checkFeed() }
        }
        .preferredColorScheme(.dark)
    }

    private var hero: some View {
        VStack(alignment: .leading, spacing: 8) {
            Eyebrow(text: "Spotify")
            Text("Elke ochtend automatisch op Spotify")
                .font(Theme.display(28))
                .foregroundStyle(Color.cream)
            Text("De studio publiceert elke dag om negen uur een nieuwe aflevering in de Grondstof-feed. Meld die feed één keer aan bij Spotify for Creators. Daarna staat elke aflevering vanzelf op Spotify, meestal binnen een uur.")
                .foregroundStyle(Color.cream.opacity(0.78))
        }
    }

    private func liveCard(_ url: URL) -> some View {
        Button { openURL(url) } label: {
            HStack(spacing: 14) {
                Image(systemName: "checkmark.seal.fill").font(.title2)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Grondstof staat live op Spotify").font(.headline)
                    Text("Open de show").font(.subheadline).opacity(0.8)
                }
                Spacer()
                Image(systemName: "arrow.up.right")
            }
            .foregroundStyle(Color.night)
            .padding(18)
            .background(Color(red: 0.12, green: 0.84, blue: 0.38), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        }
    }

    private var feedCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Eyebrow(text: "Jouw RSS-feed")
                    Spacer()
                    statusBadge
                }
                Text(feed.absoluteString)
                    .font(.system(.footnote, design: .monospaced))
                    .foregroundStyle(Color.cream)
                    .textSelection(.enabled)
                Button {
                    UIPasteboard.general.string = feed.absoluteString
                    copied = true
                    Task {
                        try? await Task.sleep(for: .seconds(2))
                        copied = false
                    }
                } label: {
                    Label(copied ? "Gekopieerd" : "Kopieer feed-URL", systemImage: copied ? "checkmark" : "doc.on.doc")
                        .contentTransition(.symbolEffect(.replace))
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Theme.fire, in: Capsule())
                        .foregroundStyle(Color.night)
                }
                .sensoryFeedback(.success, trigger: copied)
            }
        }
    }

    @ViewBuilder private var statusBadge: some View {
        switch feedStatus {
        case .checking:
            ProgressView().controlSize(.small).tint(.cream)
        case .online(let count):
            Label("\(count) afl. online", systemImage: "dot.radiowaves.up.forward")
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.amber)
        case .offline:
            Label("Nog niet bereikbaar", systemImage: "exclamationmark.triangle.fill")
                .font(.caption.weight(.semibold))
                .foregroundStyle(Color.orange)
        }
    }

    private var steps: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 16) {
                Eyebrow(text: "Eenmalig aanmelden")
                step(1, "Kopieer de feed-URL", "Gebruik de knop hierboven.")
                step(2, "Open Spotify for Creators", "Log in en kies ‘Nieuwe show’ → ‘Ik heb al een podcast’ → ‘Via RSS-feed’.")
                step(3, "Plak de feed en bevestig", "Spotify stuurt een code naar het e-mailadres uit de feed (owner_email in podcast.toml).")
                step(4, "Zet de Spotify-link in podcast.toml", "Vul spotify_url in. De app toont dan ‘Live op Spotify’ en een directe link.")
                Button { openURL(AppConfig.spotifyForCreators) } label: {
                    Label("Open Spotify for Creators", systemImage: "arrow.up.right.square")
                        .font(.subheadline.weight(.semibold))
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Color.cream.opacity(0.14), in: Capsule())
                        .foregroundStyle(Color.cream)
                }
            }
        }
    }

    private var appleCard: some View {
        GlassCard {
            VStack(alignment: .leading, spacing: 10) {
                Eyebrow(text: "Ook op Apple Podcasts")
                Text("Dezelfde feed werkt voor Apple Podcasts, Pocket Casts, Overcast en alle andere podcastapps.")
                    .font(.subheadline)
                    .foregroundStyle(Color.cream.opacity(0.8))
                Button { openURL(AppConfig.applePodcastsConnect) } label: {
                    Label("Open Apple Podcasts Connect", systemImage: "arrow.up.right.square")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(Color.amber)
                }
            }
        }
    }

    private func step(_ number: Int, _ title: String, _ detail: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Text("\(number)")
                .font(.subheadline.weight(.bold))
                .foregroundStyle(Color.night)
                .frame(width: 26, height: 26)
                .background(Theme.fire, in: Circle())
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.subheadline.weight(.semibold)).foregroundStyle(Color.cream)
                Text(detail).font(.footnote).foregroundStyle(Color.cream.opacity(0.7))
            }
        }
    }

    private func checkFeed() async {
        do {
            let (data, response) = try await URLSession.shared.data(from: feed)
            guard (response as? HTTPURLResponse)?.statusCode == 200 else { throw URLError(.badServerResponse) }
            let xml = String(decoding: data, as: UTF8.self)
            feedStatus = .online(xml.components(separatedBy: "<item>").count - 1)
        } catch {
            feedStatus = .offline
        }
    }
}
