import 'package:flutter/material.dart';

import 'api.dart';
import 'main.dart';

/// Officer confirms or overrides each field. Saved as a new review record — the original scan is never edited.
class ReviewScreen extends StatefulWidget {
  final Map<String, dynamic> scan;
  const ReviewScreen({super.key, required this.scan});
  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  late final List<Map<String, dynamic>> fields =
      (widget.scan['effective']['fields'] as List).cast<Map<String, dynamic>>();
  late final Map<String, String> _status = {for (final f in fields) f['id']: f['status']};
  final Map<String, TextEditingController> _value = {};
  final Map<String, TextEditingController> _note = {};
  final _overall = TextEditingController();
  bool _busy = false;

  TextEditingController _ctl(Map<String, TextEditingController> m, String id) => m.putIfAbsent(id, TextEditingController.new);

  Future<void> _submit() async {
    final overrides = <String, dynamic>{};
    for (final f in fields) {
      final id = f['id'] as String;
      final value = _ctl(_value, id).text.trim();
      final note = _ctl(_note, id).text.trim();
      // Send only fields the officer touched; an unchanged status still counts as "confirmed" if flagged.
      if (_status[id] != f['status'] || value.isNotEmpty || note.isNotEmpty || f['status'] != 'pass') {
        overrides[id] = {'status': _status[id], if (value.isNotEmpty) 'value': value, 'note': note};
      }
    }
    if (overrides.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Nothing to review — all fields pass.')));
      return;
    }
    setState(() => _busy = true);
    try {
      final updated = await Api.review(widget.scan['id'], overrides, _overall.text.trim());
      if (mounted) Navigator.of(context).pop(updated);
    } on ApiException catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text('Review scan #${widget.scan['id']}')),
        body: ListView(padding: const EdgeInsets.all(16), children: [
          const Text('Confirm or correct each declaration. Flagged fields are recorded as confirmed if left unchanged.'),
          const SizedBox(height: 12),
          for (final f in fields) _fieldEditor(f),
          TextField(
            controller: _overall,
            maxLines: 2,
            decoration: const InputDecoration(labelText: 'Overall review note', border: OutlineInputBorder()),
          ),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _busy ? null : _submit,
            icon: const Icon(Icons.save),
            label: Padding(padding: const EdgeInsets.all(12), child: Text(_busy ? 'Saving…' : 'Save review')),
          ),
        ]),
      );

  Widget _fieldEditor(Map<String, dynamic> f) {
    final id = f['id'] as String;
    final flagged = f['status'] != 'pass';
    return Card(
      shape: flagged
          ? RoundedRectangleBorder(side: BorderSide(color: statusColor(f['status'])), borderRadius: BorderRadius.circular(12))
          : null,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(f['label'], style: const TextStyle(fontWeight: FontWeight.w600)),
          Text('Machine read: ${f['value'] ?? '—'}  (${((f['confidence'] as num) * 100).round()}%)',
              style: const TextStyle(fontSize: 12)),
          const SizedBox(height: 8),
          SegmentedButton<String>(
            showSelectedIcon: false,
            segments: [
              for (final s in ['pass', 'review', 'fail', 'missing'])
                ButtonSegment(value: s, label: Text(statusText[s]!, style: const TextStyle(fontSize: 12))),
            ],
            selected: {_status[id]!},
            onSelectionChanged: (v) => setState(() => _status[id] = v.first),
          ),
          if (flagged || _status[id] != f['status']) ...[
            const SizedBox(height: 8),
            TextField(
              controller: _ctl(_value, id),
              decoration: const InputDecoration(labelText: 'Corrected value (optional)', isDense: true),
            ),
            TextField(
              controller: _ctl(_note, id),
              decoration: const InputDecoration(labelText: 'Note (optional)', isDense: true),
            ),
          ],
        ]),
      ),
    );
  }
}
