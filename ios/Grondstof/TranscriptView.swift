import SwiftUI

/// Meelezen: de zin die Frans uitspreekt licht op en scrolt automatisch mee. Tik om te spoelen.
struct TranscriptView: View {
    let detail: EpisodeDetail
    let currentTime: Double
    let onSeek: (Double) -> Void

    private var activeIndex: Int? { detail.cueIndex(at: currentTime) }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(showsIndicators: false) {
                LazyVStack(alignment: .leading, spacing: 10) {
                    ForEach(Array(detail.transcript.enumerated()), id: \.offset) { index, cue in
                        if index == 0 || detail.transcript[index - 1].chapter != cue.chapter {
                            header(for: detail.chapters[cue.chapter])
                        }
                        line(cue, isActive: index == activeIndex, isPast: (activeIndex ?? -1) > index)
                            .id(index)
                            .onTapGesture { onSeek(cue.start) }
                    }
                }
                .padding(.vertical, 24)
                .padding(.horizontal, 4)
            }
            .mask(
                LinearGradient(stops: [
                    .init(color: .clear, location: 0),
                    .init(color: .black, location: 0.08),
                    .init(color: .black, location: 0.88),
                    .init(color: .clear, location: 1),
                ], startPoint: .top, endPoint: .bottom)
            )
            .onChange(of: activeIndex) { _, new in
                guard let new else { return }
                withAnimation(.smooth(duration: 0.6)) { proxy.scrollTo(new, anchor: UnitPoint(x: 0.5, y: 0.35)) }
            }
            .onAppear {
                if let activeIndex { proxy.scrollTo(activeIndex, anchor: UnitPoint(x: 0.5, y: 0.35)) }
            }
        }
    }

    private func header(for chapter: Chapter) -> some View {
        HStack(spacing: 8) {
            Image(systemName: chapter.symbol)
                .font(.caption)
                .foregroundStyle(Color.amber)
            Eyebrow(text: chapter.kind == "story" ? chapter.title : chapter.kindLabel)
                .lineLimit(1)
        }
        .padding(.top, 14)
    }

    private func line(_ cue: Cue, isActive: Bool, isPast: Bool) -> some View {
        Text(cue.text)
            .font(.system(size: 21, weight: isActive ? .semibold : .regular, design: .serif))
            .foregroundStyle(Color.cream.opacity(isActive ? 1 : (isPast ? 0.45 : 0.32)))
            .scaleEffect(isActive ? 1 : 0.97, anchor: .leading)
            .frame(maxWidth: .infinity, alignment: .leading)
            .animation(.smooth(duration: 0.35), value: isActive)
            .contentShape(Rectangle())
    }
}
