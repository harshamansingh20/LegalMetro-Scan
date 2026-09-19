import 'package:flutter_test/flutter_test.dart';
import 'package:legalmetro_scan/main.dart';

void main() {
  testWidgets('login screen renders', (tester) async {
    await tester.pumpWidget(const LegalMetroApp());
    expect(find.text('LegalMetro Scan'), findsOneWidget);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
