import 'dart:io' show Platform, Process;

import 'package:flutter/foundation.dart' show kIsWeb;

Future<void> openExternalUrl(Uri uri) async {
  if (kIsWeb) {
    return;
  }

  final String url = uri.toString();
  if (Platform.isMacOS) {
    await Process.run('open', <String>[url]);
    return;
  }
  if (Platform.isWindows) {
    await Process.run('cmd', <String>[
      '/c',
      'start',
      '',
      url,
    ], runInShell: true);
    return;
  }
  if (Platform.isLinux) {
    await Process.run('xdg-open', <String>[url]);
  }
}
