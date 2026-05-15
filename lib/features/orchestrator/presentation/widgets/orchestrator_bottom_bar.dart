import 'package:flutter/material.dart';

import 'package:pulse_ai/shared/theme/tokens/governance_colors.dart';
import 'package:pulse_ai/shared/theme/tokens/governance_dimensions.dart';

final class OrchestratorBottomBar extends StatelessWidget {
  const OrchestratorBottomBar({super.key});

  @override
  Widget build(BuildContext context) {
    return const Material(
      color: GovernanceColors.surfaceContainerLowest,
      child: SizedBox(
        height: GovernanceDimensions.bottomBarHeight,
        width: double.infinity,
        child: DecoratedBox(
          decoration: BoxDecoration(
            border: Border(
              top: BorderSide(color: GovernanceColors.outlineVariant),
            ),
          ),
        ),
      ),
    );
  }
}
