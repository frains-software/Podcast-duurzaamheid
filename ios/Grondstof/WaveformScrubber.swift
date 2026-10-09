import SwiftUI

/// Tijdbalk in de vorm van de echte golfvorm van de aflevering, met hoofdstukmarkeringen.
struct WaveformScrubber: View {
    let peaks: [Double]
    let chapters: [Chapter]
    let duration: Double
    let currentTime: Double
    let onSeek: (Double) -> Void

    @State private var dragProgress: Double?

    var body: some View {
        VStack(spacing: 8) {
            GeometryReader { geo in
                let progress = dragProgress ?? (duration > 0 ? currentTime / duration : 0)
                Canvas { ctx, size in
                    let barCount = max(24, Int(size.width / 4.5))
                    let barWidth: CGFloat = size.width / CGFloat(barCount)
                    for i in 0..<barCount {
                        let value = bucket(i, of: barCount)
                        let height: CGFloat = max(3, CGFloat(value) * (size.height - 10))
                        let rect = CGRect(
                            x: CGFloat(i) * barWidth + 0.75,
                            y: (size.height - height) / 2,
                            width: max(1.5, barWidth - 1.5),
                            height: height
                        )
                        let played = Double(i) / Double(barCount) <= progress
                        let shading: GraphicsContext.Shading = played
                            ? .linearGradient(Gradient(colors: [.amber, .ember]), startPoint: .zero, endPoint: CGPoint(x: size.width, y: 0))
                            : .color(Color.cream.opacity(0.22))
                        ctx.fill(Path(roundedRect: rect, cornerRadius: 1.5), with: shading)
                    }
                    for chapter in chapters where chapter.start > 1 && duration > 0 {
                        let x = CGFloat(chapter.start / duration) * size.width
                        ctx.fill(Path(ellipseIn: CGRect(x: x - 2, y: 0, width: 4, height: 4)), with: .color(Color.cream.opacity(0.7)))
                    }
                }
                .contentShape(Rectangle())
                .gesture(
                    DragGesture(minimumDistance: 0)
                        .onChanged { value in
                            dragProgress = min(1, max(0, value.location.x / geo.size.width))
                        }
                        .onEnded { value in
                            let p = min(1, max(0, value.location.x / geo.size.width))
                            onSeek(p * duration)
                            dragProgress = nil
                        }
                )
            }
            .frame(height: 54)
            .sensoryFeedback(.selection, trigger: dragProgress == nil)

            HStack {
                Text(Formatting.clock(dragProgress.map { $0 * duration } ?? currentTime))
                Spacer()
                Text("-" + Formatting.clock(max(0, duration - (dragProgress.map { $0 * duration } ?? currentTime))))
            }
            .font(.caption.monospacedDigit())
            .foregroundStyle(Color.cream.opacity(0.65))
        }
        .accessibilityElement()
        .accessibilityLabel("Afspeelpositie")
        .accessibilityValue("\(Formatting.clock(currentTime)) van \(Formatting.clock(duration))")
        .accessibilityAdjustableAction { direction in
            switch direction {
            case .increment: onSeek(currentTime + 15)
            case .decrement: onSeek(currentTime - 15)
            @unknown default: break
            }
        }
    }

    private func bucket(_ i: Int, of count: Int) -> Double {
        guard !peaks.isEmpty else { return 0.15 }
        let from = Int(Double(i) / Double(count) * Double(peaks.count))
        let to = max(from + 1, Int(Double(i + 1) / Double(count) * Double(peaks.count)))
        return peaks[min(from, peaks.count - 1)..<min(to, peaks.count)].max() ?? 0
    }
}
