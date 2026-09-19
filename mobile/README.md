# LegalMetro Scan — mobile (Flutter)

Screens (`lib/`):
- `main.dart` — login (officer / business user) and home (scan, upload, recent scans)
- `capture_screen.dart` — camera with an on-screen framing guide; upload + progress
- `results_screen.dart` — overall status, pass/fail/missing/needs-review per declaration, confidence bars
- `review_screen.dart` — officer-only: confirm or override each field (saved as a new, append-only review)
- `api.dart` — backend client. Token is kept in memory only (closing the app signs out).

```bash
flutter pub get
flutter run --dart-define=API_URL=http://127.0.0.1:8000   # see ../README.md for emulator / device URLs
```

iOS: camera + photo-library permission strings and a local-networking ATS exception are in `ios/Runner/Info.plist`.
Android: debug builds allow cleartext HTTP to a dev backend (`android/app/src/debug/AndroidManifest.xml`); use HTTPS
for release. The camera doesn't exist on the iOS simulator — use "Upload photo" there.

Tests: `flutter test` (widget), and `flutter test test/e2e_test.dart --dart-define=E2E=true` which drives the real
results and review screens against a running backend + PaddleOCR and writes screenshots to `test/screenshots/`.
