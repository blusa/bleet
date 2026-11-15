// Run on macOS: swift assets/branding/generate.swift
// Exports the Bleet matrix + outlined rounded-system-type wordmark.
import AppKit
import CoreText

let destination = URL(fileURLWithPath: #filePath).deletingLastPathComponent()
let em: CGFloat = 112
let descriptor = NSFont.systemFont(ofSize: em, weight: .semibold).fontDescriptor.withDesign(.rounded)!
let font = NSFont(descriptor: descriptor, size: em)!
let ctFont = font as CTFont
let line = CTLineCreateWithAttributedString(NSAttributedString(string: "bleet", attributes: [.font: font, .kern: -em * 0.025]))
let text = CGMutablePath()
for run in CTLineGetGlyphRuns(line) as! [CTRun] {
    let count = CTRunGetGlyphCount(run)
    var glyphs = [CGGlyph](repeating: 0, count: count)
    var positions = [CGPoint](repeating: .zero, count: count)
    CTRunGetGlyphs(run, CFRange(location: 0, length: 0), &glyphs)
    CTRunGetPositions(run, CFRange(location: 0, length: 0), &positions)
    for i in 0..<count {
        if let path = CTFontCreatePathForGlyph(ctFont, glyphs[i], nil) {
            let translation = CGAffineTransform(translationX: positions[i].x, y: positions[i].y)
            text.addPath(path, transform: translation)
        }
    }
}
let ink = text.boundingBoxOfPath
let height: CGFloat = 144
let markSize = em * 0.86
let markX: CGFloat = 16
let markY = (height - markSize) / 2
let textX = markX + markSize + em * 0.28
let width = ceil(textX + ink.width + 18)
var transform = CGAffineTransform(a: 1, b: 0, c: 0, d: -1, tx: textX - ink.minX, ty: (height + ink.height) / 2 + ink.minY)
let outlined = text.copy(using: &transform)!
func number(_ value: CGFloat) -> String { String(format: "%.3f", value) }
var pathData = ""
outlined.applyWithBlock { pointer in
    let element = pointer.pointee
    let p = element.points
    switch element.type {
    case .moveToPoint: pathData += "M\(number(p[0].x)) \(number(p[0].y))"
    case .addLineToPoint: pathData += "L\(number(p[0].x)) \(number(p[0].y))"
    case .addQuadCurveToPoint: pathData += "Q\(number(p[0].x)) \(number(p[0].y)) \(number(p[1].x)) \(number(p[1].y))"
    case .addCurveToPoint: pathData += "C\(number(p[0].x)) \(number(p[0].y)) \(number(p[1].x)) \(number(p[1].y)) \(number(p[2].x)) \(number(p[2].y))"
    case .closeSubpath: pathData += "Z"
    @unknown default: break
    }
}
let tones: [CGFloat] = [0.34, 0.58, 0.78, 0.52, 1, 0.68, 0.78, 0.60, 0.92]
let mint = NSColor(srgbRed: 0.55, green: 0.87, blue: 0.76, alpha: 1)
let cell = em * 0.25
let gap = em * 0.055
for (name, color, hex) in [("on-dark", NSColor(srgbRed: 0.95, green: 0.97, blue: 0.96, alpha: 1), "#F2F7F5"), ("on-light", NSColor(srgbRed: 0.075, green: 0.10, blue: 0.095, alpha: 1), "#131A18")] {
    var rectangles = ""
    let bitmap = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(width * 3), pixelsHigh: Int(height * 3), bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
    let context = NSGraphicsContext.current!.cgContext
    context.scaleBy(x: 3, y: 3)
    context.translateBy(x: 0, y: height)
    context.scaleBy(x: 1, y: -1)
    for i in 0..<9 {
        let rect = CGRect(x: markX + CGFloat(i % 3) * (cell + gap), y: markY + CGFloat(i / 3) * (cell + gap), width: cell, height: cell)
        context.setFillColor(mint.withAlphaComponent(tones[i]).cgColor)
        context.addPath(CGPath(roundedRect: rect, cornerWidth: em * 0.045, cornerHeight: em * 0.045, transform: nil))
        context.fillPath()
        rectangles += "<rect x=\"\(number(rect.minX))\" y=\"\(number(rect.minY))\" width=\"\(number(cell))\" height=\"\(number(cell))\" rx=\"\(number(em * 0.045))\" fill=\"#8CDEC2\" fill-opacity=\"\(number(tones[i]))\"/>"
    }
    context.setFillColor(color.cgColor)
    context.addPath(outlined); context.fillPath()
    NSGraphicsContext.restoreGraphicsState()
    try bitmap.representation(using: .png, properties: [:])!.write(to: destination.appendingPathComponent("bleet-wordmark-\(name).png"))
    let svg = """
    <svg xmlns="http://www.w3.org/2000/svg" width="\(Int(width))" height="\(Int(height))" viewBox="0 0 \(Int(width)) \(Int(height))" role="img" aria-labelledby="title"><title id="title">Bleet</title>\(rectangles)<path fill="\(hex)" d="\(pathData)"/></svg>
    """
    try svg.write(to: destination.appendingPathComponent("bleet-wordmark-\(name).svg"), atomically: true, encoding: .utf8)
}
