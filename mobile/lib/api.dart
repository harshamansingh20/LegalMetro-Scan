import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

/// Backend base URL. iOS simulator: 127.0.0.1; Android emulator: 10.0.2.2; phone: your machine's LAN IP.
/// Override: flutter run --dart-define=API_URL=http://192.168.1.20:8000
const apiUrl = String.fromEnvironment('API_URL', defaultValue: 'http://127.0.0.1:8000');

class ApiException implements Exception {
  final String message;
  ApiException(this.message);
  @override
  String toString() => message;
}

class User {
  final int id;
  final String name, email, role;
  User.fromJson(Map<String, dynamic> j)
      : id = j['id'],
        name = j['name'],
        email = j['email'],
        role = j['role'];
  bool get isOfficer => role == 'officer';
}

/// Session token lives in memory only: closing the app logs out. Nothing sensitive is written to disk.
class Api {
  static String? _token;
  static User? user;

  static Map<String, String> get _auth => {if (_token != null) 'Authorization': 'Bearer $_token'};

  static dynamic _decode(http.Response r) {
    final body = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 400) {
      final detail = body is Map ? body['detail'] : null;
      throw ApiException(detail is String ? detail : 'Request failed (${r.statusCode})');
    }
    return body;
  }

  static Future<T> _guard<T>(Future<T> Function() f) async {
    try {
      return await f();
    } on ApiException {
      rethrow;
    } catch (e) {
      throw ApiException('Cannot reach server at $apiUrl');
    }
  }

  static Future<User> login(String email, String password) => _guard(() async {
        final r = await http.post(Uri.parse('$apiUrl/auth/login'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({'email': email.trim(), 'password': password}));
        final j = _decode(r);
        _token = j['token'];
        return user = User.fromJson(j['user']);
      });

  static void logout() {
    _token = null;
    user = null;
  }

  static Future<Map<String, dynamic>> uploadScan(Uint8List bytes) => _guard(() async {
        final req = http.MultipartRequest('POST', Uri.parse('$apiUrl/scans'))
          ..headers.addAll(_auth)
          ..files.add(http.MultipartFile.fromBytes('file', bytes,
              filename: 'label.jpg', contentType: MediaType('image', 'jpeg')));
        final r = await http.Response.fromStream(await req.send().timeout(const Duration(minutes: 2)));
        return _decode(r);
      });

  static Future<List<dynamic>> listScans() => _guard(() async =>
      _decode(await http.get(Uri.parse('$apiUrl/scans?limit=30'), headers: _auth))['items']);

  static Future<Map<String, dynamic>> getScan(int id) =>
      _guard(() async => _decode(await http.get(Uri.parse('$apiUrl/scans/$id'), headers: _auth)));

  static Future<Map<String, dynamic>> review(int id, Map<String, dynamic> overrides, String note) =>
      _guard(() async => _decode(await http.post(Uri.parse('$apiUrl/scans/$id/reviews'),
          headers: {..._auth, 'Content-Type': 'application/json'},
          body: jsonEncode({'overrides': overrides, 'note': note}))));

  static String imageUrl(int id) => '$apiUrl/scans/$id/image';
  static Map<String, String> get imageHeaders => _auth;
}
