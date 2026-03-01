import AVFoundation
import Foundation

// Read text from command-line arguments or stdin
var text: String
if CommandLine.arguments.count > 1 {
    text = CommandLine.arguments[1...].joined(separator: " ")
} else {
    var lines: [String] = []
    while let line = readLine() {
        lines.append(line)
    }
    text = lines.joined(separator: " ")
}

text = text.trimmingCharacters(in: .whitespaces)

guard !text.isEmpty else {
    fputs("Error: No text provided\n", stderr)
    exit(1)
}

let synthesizer = AVSpeechSynthesizer()
let utterance = AVSpeechUtterance(string: text)
utterance.rate = AVSpeechUtteranceDefaultSpeechRate
utterance.voice = AVSpeechSynthesisVoice(language: "en-US")

// Use a delegate + semaphore to wait for speech completion before exiting
class SpeechDelegate: NSObject, AVSpeechSynthesizerDelegate {
    let semaphore = DispatchSemaphore(value: 0)

    func speechSynthesizer(
        _ synthesizer: AVSpeechSynthesizer,
        didFinish utterance: AVSpeechUtterance
    ) {
        semaphore.signal()
    }
}

let delegate = SpeechDelegate()
synthesizer.delegate = delegate
synthesizer.speak(utterance)
delegate.semaphore.wait()
