// End-to-end: real mobile screens -> live backend -> PaddleOCR -> rules -> officer review.
// Needs the API (8000) and OCR sidecar (8001) running with the demo users from backend/README.md:
//   flutter test test/e2e_test.dart --dart-define=E2E=true
// Screenshots (real fonts) are written to test/screenshots/.
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:legalmetro_scan/api.dart';
import 'package:legalmetro_scan/main.dart';
import 'package:legalmetro_scan/results_screen.dart';

const e2e = bool.fromEnvironment('E2E');
const sample = String.fromEnvironment('SAMPLE', defaultValue: '../backend/tests/samples/hard.jpg');

Future<void> loadFonts() async {
  // Tests render text as boxes unless real fonts are loaded.
  Future<void> load(String family, String path) async {
    if (!File(path).existsSync()) return;
    final bytes = File(path).readAsBytesSync();
    await (FontLoader(family)..addFont(Future.value(ByteData.view(bytes.buffer)))).load();
  }

  await load('Roboto', '/System/Library/Fonts/Supplemental/Arial.ttf');
  await load('MaterialIcons', '${Platform.environment['FLUTTER_ROOT']}/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf');
}

Future<void> shot(WidgetTester tester, String name) async {
  final dir = Directory('test/screenshots')..createSync(recursive: true);
  FocusManager.instance.primaryFocus?.unfocus(); // no blinking cursor mid-capture
  await tester.pump(const Duration(milliseconds: 600));
  await tester.runAsync(() async {
    final img = await captureImage(tester.element(find.byType(Scaffold).last));
    final png = await img.toByteData(format: ui.ImageByteFormat.png);
    File('${dir.path}/$name.png').writeAsBytesSync(png!.buffer.asUint8List());
  });
}

void main() {
  testWidgets('scan -> results -> officer review against live backend', (tester) async {
    HttpOverrides.global = null; // flutter_test blocks real HTTP by default
    tester.view.physicalSize = const Size(390 * 3, 1100 * 3);
    tester.view.devicePixelRatio = 3;
    await loadFonts();

    // Same calls the Upload photo button makes, minus the OS file picker.
    late Map<String, dynamic> scan;
    await tester.runAsync(() async {
      await Api.login('officer@demo.in', 'Officer@123');
      scan = await Api.uploadScan(File(sample).readAsBytesSync());
    });
    expect(scan['id'], isA<int>());
    final fields = (scan['effective']['fields'] as List).cast<Map>();
    expect(fields, hasLength(7));

    await tester.pumpWidget(MaterialApp(theme: ThemeData(colorSchemeSeed: brand), home: ResultsScreen(scan: scan)));
    await tester.pump(const Duration(seconds: 1));
    expect(find.text(statusText[scan['effective']['status']]!), findsOneWidget);
    expect(find.text('Officer review'), findsOneWidget); // officer-only action
    await shot(tester, '1_results');

    // Officer review: override net quantity to Fail with a note.
    await tester.tap(find.text('Officer review'));
    await tester.pump(const Duration(seconds: 1));
    final netCard = find.ancestor(of: find.text('Net quantity (standard units)'), matching: find.byType(Card));
    await tester.ensureVisible(netCard);
    await tester.pump();
    await tester.tap(find.descendant(of: netCard, matching: find.text('Fail')));
    await tester.pump();
    await tester.enterText(find.descendant(of: netCard, matching: find.widgetWithText(TextField, 'Note (optional)')), 'Declared 500 g, weighed 468 g');
    await tester.pump();
    await shot(tester, '2_review');
    await tester.scrollUntilVisible(find.text('Save review'), 300, scrollable: find.descendant(of: find.byType(ListView), matching: find.byType(Scrollable)).first);
    await tester.tap(find.text('Save review'));
    // Let the real HTTP call finish, pumping frames until the results screen is back.
    for (var i = 0; i < 20 && find.textContaining('Review scan').evaluate().isNotEmpty; i++) {
      await tester.runAsync(() => Future.delayed(const Duration(milliseconds: 300)));
      await tester.pump(const Duration(milliseconds: 400));
    }
    await tester.pump(const Duration(seconds: 1)); // finish the pop transition

    expect(find.textContaining('weighed 468 g'), findsWidgets);
    await tester.scrollUntilVisible(find.textContaining('declarations flagged'), -300,
        scrollable: find.descendant(of: find.byType(ListView), matching: find.byType(Scrollable)).first);
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Likely non-compliant'), findsOneWidget);
    await shot(tester, '3_after_review');

    final saved = await tester.runAsync(() => Api.getScan(scan['id']));
    expect(saved!['reviews'], hasLength(1));
    expect(saved['machine_result']['status'], scan['machine_result']['status']); // original untouched
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(minutes: 3)); // let the upload's timeout timer expire
  }, skip: !e2e);
}
