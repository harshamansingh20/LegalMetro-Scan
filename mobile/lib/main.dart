import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import 'api.dart';
import 'capture_screen.dart';
import 'results_screen.dart';

void main() => runApp(const LegalMetroApp());

const brand = Color(0xFF1F4D3A);

/// Human wording for statuses. Flags read as "needs review", never "confirmed violation".
const statusText = {
  'pass': 'Pass',
  'fail': 'Fail',
  'missing': 'Missing',
  'review': 'Needs review',
  'compliant': 'Compliant',
  'needs_review': 'Needs officer review',
  'non_compliant': 'Likely non-compliant',
};

Color statusColor(String s) => switch (s) {
      'pass' || 'compliant' => const Color(0xFF1F7A4A),
      'review' || 'needs_review' => const Color(0xFF9A6200),
      _ => const Color(0xFFB3261E),
    };

IconData statusIcon(String s) => switch (s) {
      'pass' || 'compliant' => Icons.check_circle,
      'review' || 'needs_review' => Icons.help,
      'missing' => Icons.remove_circle,
      _ => Icons.cancel,
    };

class LegalMetroApp extends StatelessWidget {
  const LegalMetroApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'LegalMetro Scan',
        theme: ThemeData(colorSchemeSeed: brand, useMaterial3: true),
        home: const LoginScreen(),
      );
}

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _error;
  bool _busy = false;

  Future<void> _login() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await Api.login(_email.text, _password.text);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const HomeScreen()));
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(28),
              child: AutofillGroup(
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  const Icon(Icons.document_scanner, size: 56, color: brand),
                  const SizedBox(height: 12),
                  Text('LegalMetro Scan',
                      textAlign: TextAlign.center, style: Theme.of(context).textTheme.headlineMedium),
                  const Text('Legal Metrology label compliance check', textAlign: TextAlign.center),
                  const SizedBox(height: 28),
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    decoration: const InputDecoration(labelText: 'Email', border: OutlineInputBorder()),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _password,
                    obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    onSubmitted: (_) => _login(),
                    decoration: const InputDecoration(labelText: 'Password', border: OutlineInputBorder()),
                  ),
                  if (_error != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: Text(_error!, style: const TextStyle(color: Color(0xFFB3261E))),
                    ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: _busy ? null : _login,
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Text(_busy ? 'Signing in…' : 'Sign in'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  const Text('Officers can review and override results; business users can self-check their labels.',
                      textAlign: TextAlign.center, style: TextStyle(fontSize: 12)),
                ]),
              ),
            ),
          ),
        ),
      );
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<dynamic>> _scans = Api.listScans();

  void _refresh() => setState(() => _scans = Api.listScans());

  Future<void> _openCamera() async {
    final scan = await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(builder: (_) => const CaptureScreen()));
    if (scan != null) _showResult(scan);
  }

  Future<void> _pickFromGallery() async {
    // image_picker re-encodes to JPEG and downsizes — plenty for OCR, much faster to upload.
    final f = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 2000, maxHeight: 2000, imageQuality: 88);
    if (f == null || !mounted) return;
    final scan = await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(builder: (_) => UploadingScreen(bytes: f.readAsBytes())));
    if (scan != null) _showResult(scan);
  }

  Future<void> _showResult(Map<String, dynamic> scan) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ResultsScreen(scan: scan)));
    _refresh();
  }

  @override
  Widget build(BuildContext context) {
    final user = Api.user!;
    return Scaffold(
      appBar: AppBar(
        title: const Text('LegalMetro Scan'),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () {
              Api.logout();
              Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
            },
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async => _refresh(),
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Text('${user.name} · ${user.isOfficer ? 'Officer' : 'Business self-check'}',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(
              child: FilledButton.icon(
                onPressed: _openCamera,
                icon: const Icon(Icons.photo_camera),
                label: const Padding(padding: EdgeInsets.symmetric(vertical: 14), child: Text('Scan label')),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: OutlinedButton.icon(
                onPressed: _pickFromGallery,
                icon: const Icon(Icons.photo_library),
                label: const Padding(padding: EdgeInsets.symmetric(vertical: 14), child: Text('Upload photo')),
              ),
            ),
          ]),
          const SizedBox(height: 24),
          Text(user.isOfficer ? 'Recent scans (all users)' : 'Your recent scans',
              style: Theme.of(context).textTheme.titleSmall),
          FutureBuilder(
            future: _scans,
            builder: (context, snap) {
              if (snap.hasError) return Padding(padding: const EdgeInsets.all(16), child: Text('${snap.error}'));
              if (!snap.hasData) return const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator()));
              if (snap.data!.isEmpty) return const Padding(padding: EdgeInsets.all(24), child: Text('No scans yet.'));
              return Column(
                children: [
                  for (final s in snap.data!)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(statusIcon(s['status']), color: statusColor(s['status'])),
                      title: Text(s['commodity'] ?? 'Scan #${s['id']}'),
                      subtitle: Text('#${s['id']} · ${statusText[s['status']]}${s['reviewed'] ? ' · reviewed' : ''}'),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () async {
                        try {
                          _showResult(await Api.getScan(s['id']));
                        } on ApiException catch (e) {
                          if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
                        }
                      },
                    ),
                ],
              );
            },
          ),
        ]),
      ),
    );
  }
}
