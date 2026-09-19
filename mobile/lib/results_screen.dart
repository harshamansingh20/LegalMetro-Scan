import 'package:flutter/material.dart';

import 'api.dart';
import 'main.dart';
import 'review_screen.dart';

class ResultsScreen extends StatefulWidget {
  final Map<String, dynamic> scan;
  const ResultsScreen({super.key, required this.scan});
  @override
  State<ResultsScreen> createState() => _ResultsScreenState();
}

class _ResultsScreenState extends State<ResultsScreen> {
  late Map<String, dynamic> scan = widget.scan;

  Future<void> _review() async {
    final updated = await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(builder: (_) => ReviewScreen(scan: scan)));
    if (updated != null) setState(() => scan = updated);
  }

  @override
  Widget build(BuildContext context) {
    final eff = scan['effective'] as Map<String, dynamic>;
    final fields = (eff['fields'] as List).cast<Map<String, dynamic>>();
    final status = eff['status'] as String;
    final flagged = fields.where((f) => f['status'] != 'pass').length;

    return Scaffold(
      appBar: AppBar(title: Text('Scan #${scan['id']}')),
      floatingActionButton: Api.user!.isOfficer
          ? FloatingActionButton.extended(
              onPressed: _review,
              icon: const Icon(Icons.fact_check),
              label: const Text('Officer review'),
            )
          : null,
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 16, 16, 96), children: [
        Card(
          color: statusColor(status).withValues(alpha: 0.1),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(children: [
              Icon(statusIcon(status), color: statusColor(status), size: 40),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(statusText[status]!,
                      style: Theme.of(context).textTheme.titleLarge!.copyWith(color: statusColor(status))),
                  Text(flagged == 0
                      ? 'All 7 declarations found and well-formed.'
                      : '$flagged of ${fields.length} declarations flagged for review.'),
                  Text(eff['reviewed'] == true ? 'Officer reviewed' : 'Automated check — not yet officer reviewed',
                      style: const TextStyle(fontSize: 12)),
                ]),
              ),
            ]),
          ),
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: Image.network(Api.imageUrl(scan['id']),
              headers: Api.imageHeaders,
              height: 180,
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => const SizedBox.shrink()),
        ),
        const SizedBox(height: 8),
        for (final f in fields) FieldCard(field: f),
        const Padding(
          padding: EdgeInsets.all(8),
          child: Text(
            'Decision support only: a flag means "needs review", not a confirmed violation. '
            'Font-size checks are approximate. This does not verify product authenticity.',
            style: TextStyle(fontSize: 12),
          ),
        ),
      ]),
    );
  }
}

class FieldCard extends StatelessWidget {
  final Map<String, dynamic> field;
  const FieldCard({super.key, required this.field});

  @override
  Widget build(BuildContext context) {
    final s = field['status'] as String;
    final conf = (field['confidence'] as num).toDouble();
    final reviewed = field['reviewed'] as Map<String, dynamic>?;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(statusIcon(s), color: statusColor(s), semanticLabel: statusText[s]),
            const SizedBox(width: 8),
            Expanded(child: Text(field['label'], style: const TextStyle(fontWeight: FontWeight.w600))),
            Text(statusText[s]!, style: TextStyle(color: statusColor(s), fontWeight: FontWeight.w600)),
          ]),
          if (field['value'] != null)
            Padding(padding: const EdgeInsets.only(top: 6), child: Text(field['value'])),
          const SizedBox(height: 8),
          Row(children: [
            const Text('Confidence ', style: TextStyle(fontSize: 12)),
            Expanded(
              child: LinearProgressIndicator(
                value: conf,
                minHeight: 6,
                borderRadius: BorderRadius.circular(3),
                color: conf >= 0.8 ? const Color(0xFF1F7A4A) : conf >= 0.5 ? const Color(0xFFD49B20) : const Color(0xFFB3261E),
                backgroundColor: Colors.black12,
              ),
            ),
            Text(' ${(conf * 100).round()}%', style: const TextStyle(fontSize: 12)),
          ]),
          for (final m in (field['messages'] as List))
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('• $m', style: const TextStyle(fontSize: 13, color: Color(0xFF9A6200))),
            ),
          if (reviewed != null)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(
                'Officer ${reviewed['by']}: ${statusText[reviewed['machine_status']]} → ${statusText[s]}'
                '${(reviewed['note'] as String).isNotEmpty ? ' — ${reviewed['note']}' : ''}',
                style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic),
              ),
            ),
        ]),
      ),
    );
  }
}
