import AppIntents
import SwiftUI

@main
struct GrondstofApp: App {
    @Environment(\.scenePhase) private var scenePhase
    private var model: AppModel { AppModel.shared }

    var body: some Scene {
        WindowGroup {
            HomeView()
                .environment(model.store)
                .environment(model.player)
                .preferredColorScheme(.dark)
                .tint(.ember)
                .task { await model.store.refresh() }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { Task { await model.store.refresh() } }
        }
    }
}

/// Gedeelde staat, zodat ook Siri en Opdrachten de speler kunnen bedienen.
@MainActor
final class AppModel {
    static let shared = AppModel()
    let store = EpisodeStore()
    let player = AudioPlayer()

    func playLatest() async {
        if store.latest == nil { await store.refresh() }
        guard let latest = store.latest else { return }
        await player.play(latest, store: store)
    }
}

// MARK: - Siri en Opdrachten: "Hé Siri, speel Grondstof"

struct PlayLatestEpisodeIntent: AppIntent {
    static let title: LocalizedStringResource = "Speel de nieuwste Grondstof"
    static let description: IntentDescription = IntentDescription("Start de nieuwste aflevering van Grondstof.")
    static let openAppWhenRun = true

    @MainActor
    func perform() async throws -> some IntentResult {
        await AppModel.shared.playLatest()
        return .result()
    }
}

struct GrondstofShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: PlayLatestEpisodeIntent(),
            phrases: [
                "Speel \(.applicationName)",
                "Start \(.applicationName)",
                "Speel het nieuws van \(.applicationName)",
            ],
            shortTitle: "Speel Grondstof",
            systemImageName: "play.circle.fill"
        )
    }
}
