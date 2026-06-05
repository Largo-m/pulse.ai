import 'dart:io';

import 'package:flutter/services.dart';
import 'package:pulse_ai/features/orchestrator/domain/service/project_sandbox_access_service.dart';

final class ProjectSandboxAccessServiceImpl
    implements ProjectSandboxAccessService {
  ProjectSandboxAccessServiceImpl({
    MethodChannel? bookmarkChannel,
    bool Function()? isMacOS,
  }) : _channel =
           bookmarkChannel ??
           const MethodChannel('pulse_ai/security_scoped_bookmark'),
       _isMacOS = isMacOS ?? (() => Platform.isMacOS);

  final MethodChannel _channel;
  final bool Function() _isMacOS;

  @override
  Future<String?> createBookmark(String absolutePath) async {
    if (!_isMacOS()) {
      return null;
    }

    try {
      final String? bookmark = await _channel.invokeMethod<String>(
        'createBookmark',
        <String, String>{'path': absolutePath},
      );
      return bookmark;
    } on PlatformException {
      return null;
    }
  }

  @override
  Future<bool> startAccess({
    required String? macosSecurityScopedBookmark,
  }) async {
    if (!_isMacOS() || macosSecurityScopedBookmark == null) {
      return true;
    }

    try {
      final bool? accessed = await _channel.invokeMethod<bool>(
        'startAccess',
        <String, String>{'bookmark': macosSecurityScopedBookmark},
      );
      return accessed ?? false;
    } on PlatformException {
      return false;
    }
  }

  @override
  Future<void> stopAccess() async {
    if (!_isMacOS()) {
      return;
    }

    try {
      await _channel.invokeMethod<void>('stopAccess');
    } on PlatformException {
      return;
    }
  }
}
