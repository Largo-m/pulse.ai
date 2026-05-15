import 'package:flutter/material.dart';

import 'governance_typography.dart';
import 'tokens/governance_colors.dart';

abstract final class GovernanceThemeData {
  static ThemeData build() {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: GovernanceColors.colorScheme,
      scaffoldBackgroundColor: GovernanceColors.background,
      textTheme: GovernanceTypography.textTheme,
    );
  }
}
