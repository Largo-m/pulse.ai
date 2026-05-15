import 'package:shared_preferences/shared_preferences.dart';

final class RecentProjectsLocalStorage {
  RecentProjectsLocalStorage(this._preferences);

  static const String storageKey = 'orchestrator.recent_projects.v1';

  final SharedPreferences _preferences;

  String? readRaw() {
    return _preferences.getString(storageKey);
  }

  Future<void> writeRaw(String rawJson) async {
    await _preferences.setString(storageKey, rawJson);
  }

  Future<void> clear() async {
    await _preferences.remove(storageKey);
  }
}
