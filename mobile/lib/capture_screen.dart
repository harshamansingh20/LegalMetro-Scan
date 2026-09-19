import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import 'api.dart';

/// Camera with an on-screen framing guide (stands in for automatic label localisation, which is future work).
class CaptureScreen extends StatefulWidget {
  const CaptureScreen({super.key});
  @override
  State<CaptureScreen> createState() => _CaptureScreenState();
}

class _CaptureScreenState extends State<CaptureScreen> {
  CameraController? _cam;
  String? _error;

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    try {
      final cams = await availableCameras();
      if (cams.isEmpty) throw CameraException('none', 'No camera on this device');
      final back = cams.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cams.first);
      final cam = CameraController(back, ResolutionPreset.veryHigh, enableAudio: false, imageFormatGroup: ImageFormatGroup.jpeg);
      await cam.initialize();
      if (!mounted) return await cam.dispose();
      setState(() => _cam = cam);
    } on CameraException catch (e) {
      setState(() => _error = '${e.description ?? e.code}. Use "Upload photo" instead.');
    }
  }

  @override
  void dispose() {
    _cam?.dispose();
    super.dispose();
  }

  Future<void> _shoot() async {
    final shot = await _cam!.takePicture();
    if (!mounted) return;
    final scan = await Navigator.of(context).push<Map<String, dynamic>>(
        MaterialPageRoute(builder: (_) => UploadingScreen(bytes: shot.readAsBytes())));
    if (mounted && scan != null) Navigator.of(context).pop(scan);
  }

  @override
  Widget build(BuildContext context) {
    final cam = _cam;
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(title: const Text('Scan label'), backgroundColor: Colors.black, foregroundColor: Colors.white),
      body: _error != null
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(_error!, style: const TextStyle(color: Colors.white))))
          : cam == null
              ? const Center(child: CircularProgressIndicator())
              : Stack(fit: StackFit.expand, children: [
                  Center(child: CameraPreview(cam)),
                  // Framing guide.
                  IgnorePointer(
                    child: Center(
                      child: FractionallySizedBox(
                        widthFactor: 0.88,
                        heightFactor: 0.55,
                        child: Container(
                          decoration: BoxDecoration(border: Border.all(color: Colors.white, width: 3), borderRadius: BorderRadius.circular(12)),
                        ),
                      ),
                    ),
                  ),
                  const Positioned(
                    top: 16,
                    left: 16,
                    right: 16,
                    child: Text(
                      'Fit the full declaration panel inside the frame.\nHold steady, avoid glare, fill the frame.',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: Colors.white, fontSize: 15, shadows: [Shadow(blurRadius: 4)]),
                    ),
                  ),
                  Positioned(
                    bottom: 32,
                    left: 0,
                    right: 0,
                    child: Center(
                      child: FloatingActionButton.large(
                        tooltip: 'Capture',
                        onPressed: _shoot,
                        child: const Icon(Icons.camera),
                      ),
                    ),
                  ),
                ]),
    );
  }
}

/// Uploads the photo, waits for OCR + rule check, then pops with the scan detail.
class UploadingScreen extends StatefulWidget {
  final Future<Uint8List> bytes;
  const UploadingScreen({super.key, required this.bytes});
  @override
  State<UploadingScreen> createState() => _UploadingScreenState();
}

class _UploadingScreenState extends State<UploadingScreen> {
  String? _error;

  @override
  void initState() {
    super.initState();
    _upload();
  }

  Future<void> _upload() async {
    if (_error != null) setState(() => _error = null);
    try {
      final scan = await Api.uploadScan(await widget.bytes);
      if (mounted) Navigator.of(context).pop(scan);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('Checking label')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: _error == null
                ? const Column(mainAxisSize: MainAxisSize.min, children: [
                    CircularProgressIndicator(),
                    SizedBox(height: 16),
                    Text('Reading label (OCR) and checking the 7 mandatory declarations…', textAlign: TextAlign.center),
                  ])
                : Column(mainAxisSize: MainAxisSize.min, children: [
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton(onPressed: _upload, child: const Text('Retry')),
                  ]),
          ),
        ),
      );
}
