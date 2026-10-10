import SwiftUI
import UserNotifications

struct SettingsView: View {
    @Environment(EpisodeStore.self) private var store
    @Environment(AudioPlayer.self) private var player
    @Environment(\.dismiss) private var dismiss
    @AppStorage("reminderEnabled") private var reminderEnabled = false
    @AppStorage("siteURL") private var siteURL = ""

    var body: some View {
        @Bindable var player = player
        NavigationStack {
            Form {
                Section {
                    Toggle(isOn: $reminderEnabled) {
                        Label("Seintje om \(String(format: "%02d:%02d", AppConfig.reminderHour, AppConfig.reminderMinute))", systemImage: "bell.badge.fill")
                    }
                    .tint(.ember)
                    .onChange(of: reminderEnabled) { _, enabled in
                        Task {
                            if enabled {
                                reminderEnabled = await DailyReminder.enable()
                            } else {
                                DailyReminder.disable()
                            }
                        }
                    }
                    Picker(selection: $player.rate) {
                        ForEach(AudioPlayer.rates.sorted(), id: \.self) { rate in
                            Text(String(format: "%.2f×", rate).replacingOccurrences(of: ".", with: ",")).tag(rate)
                        }
                    } label: {
                        Label("Afspeelsnelheid", systemImage: "gauge.with.dots.needle.67percent")
                    }
                } header: {
                    Text("Luisteren")
                } footer: {
                    Text("Elke ochtend een melding zodra de nieuwe Grondstof klaarstaat.")
                }

                Section("Over Grondstof") {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(store.show?.subtitle ?? "Elke ochtend vijf minuten circulair nieuws")
                            .font(.headline)
                        Text(store.show?.description ?? "")
                            .font(.footnote)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 4)
                    LabeledContent("Presentatie", value: store.show?.host ?? "Frans van den Berge")
                    LabeledContent("Namens", value: store.show?.organisation ?? "De Graaf Groep")
                    Link(destination: store.show?.linkedInURL ?? AppConfig.linkedIn) {
                        Label("Frans van den Berge op LinkedIn", systemImage: "person.crop.square")
                    }
                    if let site = store.show?.websiteURL {
                        Link(destination: site) { Label("Website en webspeler", systemImage: "safari") }
                    }
                }

                Section {
                    TextField("https://…", text: $siteURL)
                        .keyboardType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                    Button("Afleveringen opnieuw laden") { Task { await store.refresh() } }
                } header: {
                    Text("Bron (geavanceerd)")
                } footer: {
                    Text("Leeg laten voor de standaardfeed: \(AppConfig.defaultSiteURL.absoluteString)")
                }
            }
            .scrollContentBackground(.hidden)
            .background(AuroraBackground().opacity(0.6))
            .navigationTitle("Instellingen")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Klaar") { dismiss() } }
            }
        }
        .preferredColorScheme(.dark)
    }
}

enum DailyReminder {
    static let identifier = "grondstof.daily"

    static func enable() async -> Bool {
        let center = UNUserNotificationCenter.current()
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        guard granted else { return false }
        let content = UNMutableNotificationContent()
        content.title = "Goedemorgen, de nieuwe Grondstof staat klaar"
        content.body = "Vijf minuten nieuws over duurzaamheid en circulaire economie."
        content.sound = .default
        var when = DateComponents()
        when.hour = AppConfig.reminderHour
        when.minute = AppConfig.reminderMinute
        let trigger = UNCalendarNotificationTrigger(dateMatching: when, repeats: true)
        let request = UNNotificationRequest(identifier: identifier, content: content, trigger: trigger)
        do {
            try await center.add(request)
            return true
        } catch {
            return false
        }
    }

    static func disable() {
        UNUserNotificationCenter.current().removePendingNotificationRequests(withIdentifiers: [identifier])
    }
}
