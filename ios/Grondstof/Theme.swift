import SwiftUI

extension Color {
    static let night = Color(red: 20 / 255, green: 7 / 255, blue: 31 / 255)
    static let aubergine = Color(red: 46 / 255, green: 12 / 255, blue: 74 / 255)
    static let grape = Color(red: 90 / 255, green: 24 / 255, blue: 154 / 255)
    static let violet = Color(red: 109 / 255, green: 40 / 255, blue: 217 / 255)
    static let orchid = Color(red: 168 / 255, green: 85 / 255, blue: 247 / 255)
    static let ember = Color(red: 255 / 255, green: 106 / 255, blue: 26 / 255)
    static let amber = Color(red: 255 / 255, green: 181 / 255, blue: 71 / 255)
    static let cream = Color(red: 255 / 255, green: 244 / 255, blue: 230 / 255)
}

enum Theme {
    static let fire = LinearGradient(colors: [.amber, .ember], startPoint: .topLeading, endPoint: .bottomTrailing)
    static let dusk = LinearGradient(colors: [.violet, .ember], startPoint: .leading, endPoint: .trailing)

    static func display(_ size: CGFloat) -> Font { .system(size: size, weight: .semibold, design: .serif) }
    static func eyebrow() -> Font { .system(size: 12, weight: .semibold).width(.expanded) }
}

/// Een levende paars-oranje achtergrond. `energy` (0…1) laat hem meebewegen met de stem.
struct AuroraBackground: View {
    var energy: Double = 0
    var isActive: Bool = false

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30.0)) { context in
            let t = context.date.timeIntervalSinceReferenceDate * (isActive ? 0.55 : 0.18)
            ZStack {
                MeshGradient(
                    width: 3,
                    height: 3,
                    points: Self.points(t: t, energy: energy),
                    colors: Self.colors(t: t, energy: energy),
                    smoothsColors: true
                )
                RadialGradient(
                    colors: [Color.amber.opacity(0.10 + 0.25 * energy), .clear],
                    center: .init(x: 0.5, y: 0.38),
                    startRadius: 10,
                    endRadius: 260 + 140 * energy
                )
                .blendMode(.plusLighter)
                LinearGradient(colors: [.clear, Color.night.opacity(0.55)], startPoint: .center, endPoint: .bottom)
            }
        }
        .ignoresSafeArea()
    }

    private static func points(t: Double, energy: Double) -> [SIMD2<Float>] {
        let a = Float(0.06 + 0.07 * energy)
        func wobble(_ phase: Double, _ speed: Double) -> Float { Float(sin(t * speed + phase)) * a }
        return [
            SIMD2(0, 0), SIMD2(0.5 + wobble(0, 0.9), 0), SIMD2(1, 0),
            SIMD2(0, 0.5 + wobble(1.3, 0.7)), SIMD2(0.5 + wobble(2.1, 1.1), 0.45 + wobble(0.4, 0.8)), SIMD2(1, 0.5 + wobble(2.9, 0.6)),
            SIMD2(0, 1), SIMD2(0.5 + wobble(3.7, 0.75), 1), SIMD2(1, 1),
        ]
    }

    private static func colors(t: Double, energy: Double) -> [Color] {
        let pulse = 0.5 + 0.5 * sin(t * 0.8)
        let warm = Color.ember.opacity(0.75 + 0.25 * energy)
        return [
            .violet, .grape, .aubergine,
            .aubergine, Color.orchid.opacity(0.55 + 0.25 * pulse), .grape,
            .night, warm, .amber.opacity(0.85),
        ]
    }
}

/// Glazen kaart in de stijl van de app.
struct GlassCard<Content: View>: View {
    var padding: CGFloat = 20
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(padding)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.ultraThinMaterial.opacity(0.85), in: RoundedRectangle(cornerRadius: 26, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 26, style: .continuous)
                    .strokeBorder(Color.cream.opacity(0.14), lineWidth: 1)
            )
    }
}

struct Eyebrow: View {
    let text: String
    var color: Color = .amber

    var body: some View {
        Text(text.uppercased())
            .font(Theme.eyebrow())
            .tracking(1.6)
            .foregroundStyle(color)
    }
}
