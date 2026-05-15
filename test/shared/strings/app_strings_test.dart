import 'package:flutter_test/flutter_test.dart';

import 'package:pulse_ai/shared/strings/app_strings.dart';

void main() {
  group('AppStrings', () {
    test('windowTitle and homeTitle share the product name', () {
      expect(AppStrings.windowTitle, AppStrings.homeTitle);
      expect(AppStrings.windowTitle, isNotEmpty);
    });
  });
}
