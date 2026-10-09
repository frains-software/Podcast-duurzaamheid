import SwiftUI

struct MiniPlayer: View {
    @Environment(AudioPlayer.self) private var player
    let onExpand: () -> Void

    var body: some View {
        if let episode = player.episode {
            HStack(spacing: 12) {
                Image("Kringloop")
                    .resizable()
                    .frame(width: 40, height: 40)
                    .rotationEffect(.degrees(player.currentTime * 6))
                    .animation(.linear(duration: 0.1), value: player.currentTime)
                VStack(alignment: .leading, spacing: 2) {
                    Text(episode.title)
                        .font(.subheadline.weight(.semibold))
                        .lineLimit(1)
                    Text(player.currentChapter?.title ?? "Grondstof")
                        .font(.caption)
                        .foregroundStyle(Color.amber)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                Button { player.toggle() } label: {
                    Image(systemName: player.isPlaying ? "pause.fill" : "play.fill")
                        .font(.title3)
                        .contentTransition(.symbolEffect(.replace))
                        .frame(width: 44, height: 44)
                }
                .accessibilityLabel(player.isPlaying ? "Pauzeer" : "Speel af")
            }
            .foregroundStyle(Color.cream)
            .padding(.leading, 10)
            .padding(.trailing, 6)
            .padding(.vertical, 8)
            .background {
                ZStack(alignment: .bottomLeading) {
                    RoundedRectangle(cornerRadius: 22, style: .continuous).fill(.ultraThinMaterial)
                    GeometryReader { geo in
                        Capsule()
                            .fill(Theme.fire)
                            .frame(width: geo.size.width * player.progress, height: 3)
                            .frame(maxHeight: .infinity, alignment: .bottom)
                    }
                    .padding(.horizontal, 18)
                    .padding(.bottom, 1)
                }
            }
            .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color.cream.opacity(0.12)))
            .shadow(color: .black.opacity(0.35), radius: 18, y: 8)
            .contentShape(Rectangle())
            .onTapGesture(perform: onExpand)
        }
    }
}
