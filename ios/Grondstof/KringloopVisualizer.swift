import SwiftUI

/// De 'kringloop': drie draaiende pijlen rond een ring van golfvormstaven die op de stem
/// van Frans reageren, met deeltjes die als grondstoffen rondcirkelen. De energie komt uit
/// de golfvorm die de studio vooraf berekent; daardoor is de animatie echt synchroon met de audio.
struct KringloopVisualizer: View {
    let detail: EpisodeDetail?
    /// Geeft de afspeelpositie op een gegeven moment; zo loopt de animatie vloeiend tussen de tijdsupdates door.
    let time: (Date) -> Double
    let isPlaying: Bool
    var label: String = ""

    private static let barCount = 84
    private static let particles: [(radius: CGFloat, speed: Double, phase: Double, size: CGFloat)] = (0..<26).map { i in
        let r = 0.62 + 0.36 * CGFloat((i * 37 % 100)) / 100
        return (r, 0.08 + Double(i % 7) * 0.025, Double(i) * 0.97, 1.5 + CGFloat(i % 4))
    }

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 60.0, paused: !isPlaying)) { context in
            let clock = context.date.timeIntervalSinceReferenceDate
            let now = time(context.date)
            let level = detail?.level(at: now) ?? 0
            let bars = detail?.window(around: now, count: Self.barCount, span: 7) ?? Array(repeating: 0.12, count: Self.barCount)
            Canvas { ctx, size in
                draw(in: &ctx, size: size, clock: clock, now: now, level: level, bars: bars)
            }
            .overlay {
                core(level: level)
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityElement()
        .accessibilityLabel(isPlaying ? "Visualisatie van de aflevering, speelt af" : "Visualisatie van de aflevering")
    }

    private func core(level: Double) -> some View {
        ZStack {
            Circle()
                .fill(RadialGradient(colors: [.amber, .ember, Color.ember.opacity(0)], center: .center, startRadius: 2, endRadius: 90))
                .scaleEffect(0.82 + 0.28 * level)
                .blur(radius: 10)
                .opacity(0.55 + 0.45 * level)
            VStack(spacing: 2) {
                Text(label)
                    .font(Theme.display(30))
                    .foregroundStyle(Color.cream)
                    .contentTransition(.numericText())
                Text("GRONDSTOF")
                    .font(.system(size: 9, weight: .bold).width(.expanded))
                    .tracking(2)
                    .foregroundStyle(Color.cream.opacity(0.75))
            }
        }
        .frame(width: 150, height: 150)
        .animation(.easeOut(duration: 0.12), value: level)
    }

    private func draw(in ctx: inout GraphicsContext, size: CGSize, clock: Double, now: Double, level: Double, bars: [Double]) {
        let side: CGFloat = min(size.width, size.height)
        let center = CGPoint(x: size.width / 2, y: size.height / 2)
        let ringRadius: CGFloat = side * 0.29
        let arcRadius: CGFloat = side * 0.43
        let spin: Double = clock * (isPlaying ? 0.35 : 0.06)
        let total: Double = detail?.duration ?? 0
        let progress: Double = total > 0 ? min(1, now / total) : 0

        // 1. Golfvormring
        let count = bars.count
        for i in 0..<count {
            let angle: Double = Double(i) / Double(count) * 2 * .pi - .pi / 2 + spin * 0.25
            let value: CGFloat = CGFloat(max(0.06, bars[i]))
            let inner: CGFloat = ringRadius
            let outer: CGFloat = ringRadius + side * 0.09 * value + 2
            let cosA = CGFloat(cos(angle))
            let sinA = CGFloat(sin(angle))
            var path = Path()
            path.move(to: CGPoint(x: center.x + cosA * inner, y: center.y + sinA * inner))
            path.addLine(to: CGPoint(x: center.x + cosA * outer, y: center.y + sinA * outer))
            let warmth = Double(i) / Double(count)
            let color = Color(
                red: 1.0,
                green: 0.42 + 0.29 * warmth,
                blue: 0.10 + 0.18 * warmth
            ).opacity(0.35 + 0.65 * Double(value))
            ctx.stroke(path, with: .color(color), style: StrokeStyle(lineWidth: max(2, side * 0.008), lineCap: .round))
        }

        // 2. Voortgangsring
        var track = Path()
        track.addArc(center: center, radius: ringRadius - side * 0.035, startAngle: .degrees(0), endAngle: .degrees(360), clockwise: false)
        ctx.stroke(track, with: .color(Color.cream.opacity(0.10)), lineWidth: 2)
        if progress > 0 {
            var done = Path()
            done.addArc(center: center, radius: ringRadius - side * 0.035, startAngle: .degrees(-90),
                        endAngle: .degrees(-90 + 360 * progress), clockwise: false)
            ctx.stroke(done, with: .linearGradient(Gradient(colors: [.amber, .ember]),
                                                   startPoint: CGPoint(x: 0, y: 0),
                                                   endPoint: CGPoint(x: size.width, y: size.height)),
                       style: StrokeStyle(lineWidth: 3, lineCap: .round))
        }

        // 3. De drie pijlen van de kringloop
        let lineWidth: CGFloat = side * 0.022
        for k in 0..<3 {
            let startDeg: Double = Double(k) * 120 + 12 + spin * 57.3
            let endDeg: Double = startDeg + 92
            var arc = Path()
            arc.addArc(center: center, radius: arcRadius, startAngle: .degrees(startDeg), endAngle: .degrees(endDeg), clockwise: false)
            let tint: Color = k == 0 ? .amber : .cream
            ctx.stroke(arc, with: .color(tint.opacity(0.92)), style: StrokeStyle(lineWidth: lineWidth, lineCap: .round))
            ctx.fill(arrowHead(center: center, radius: arcRadius, degrees: endDeg, size: lineWidth * 1.6), with: .color(tint))
        }

        // 4. Rondcirkelende deeltjes
        for p in Self.particles {
            let angle: Double = clock * p.speed * (0.4 + 1.6 * level) + p.phase
            let r: CGFloat = side * 0.5 * p.radius
            let point = CGPoint(x: center.x + CGFloat(cos(angle)) * r, y: center.y + CGFloat(sin(angle)) * r)
            let dot = CGRect(x: point.x - p.size / 2, y: point.y - p.size / 2, width: p.size, height: p.size)
            ctx.fill(Path(ellipseIn: dot), with: .color(Color.cream.opacity(0.25 + 0.5 * level)))
        }
    }

    private func arrowHead(center: CGPoint, radius: CGFloat, degrees: Double, size: CGFloat) -> Path {
        let a = degrees * .pi / 180
        let tipAngle = (degrees + 7) * .pi / 180
        let base = CGPoint(x: center.x + radius * CGFloat(cos(a)), y: center.y + radius * CGFloat(sin(a)))
        let tip = CGPoint(x: center.x + radius * CGFloat(cos(tipAngle)), y: center.y + radius * CGFloat(sin(tipAngle)))
        let normal = CGPoint(x: CGFloat(cos(a)), y: CGFloat(sin(a)))
        var path = Path()
        path.move(to: CGPoint(x: base.x + normal.x * size, y: base.y + normal.y * size))
        path.addLine(to: tip)
        path.addLine(to: CGPoint(x: base.x - normal.x * size, y: base.y - normal.y * size))
        path.closeSubpath()
        return path
    }
}
