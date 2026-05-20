import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pulse_ai/app/di/hive_bootstrap.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const MethodChannel pathProviderChannel = MethodChannel(
    'plugins.flutter.io/path_provider',
  );

  setUp(() {
    HiveBootstrap.resetForTesting();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(pathProviderChannel, (
          MethodCall methodCall,
        ) async {
          if (methodCall.method == 'getApplicationDocumentsDirectory') {
            return '/tmp/pulse_hive_test';
          }
          return null;
        });
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(pathProviderChannel, null);
  });

  group('HiveBootstrap', () {
    test('ensureInitialized completes without error on first call', () async {
      await expectLater(HiveBootstrap.ensureInitialized(), completes);
    });

    test(
      'ensureInitialized does not throw on second call in same process',
      () async {
        await HiveBootstrap.ensureInitialized();
        await expectLater(HiveBootstrap.ensureInitialized(), completes);
      },
    );
  });
}
