import 'package:flutter/material.dart';

import 'pulse_typography.dart';
import 'tokens/pulse_colors.dart';

abstract final class PulseThemeData {
  static ThemeData build() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: PulseColors.colorScheme,
      scaffoldBackgroundColor: PulseColors.background,
      textTheme: PulseTypography.textTheme,
    );
  }
}
