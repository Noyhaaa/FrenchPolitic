import { StyleSheet, Text, View } from 'react-native';
import { radius } from '@/theme';
import { ThemeScrutin } from '@/types';
import { themeEmoji, themeTint } from '@/constants/themes';

interface Props {
  theme: ThemeScrutin;
  size?: number;
}

/** Pastille emoji illustrant le thème du scrutin (coin des cartes). */
export function ThemeAvatar({ theme, size = 44 }: Props) {
  return (
    <View
      style={[
        styles.container,
        {
          width: size,
          height: size,
          borderRadius: radius.md,
          backgroundColor: themeTint[theme] ?? themeTint.Autre,
        },
      ]}
      accessibilityElementsHidden
      importantForAccessibility="no"
    >
      <Text style={{ fontSize: size * 0.45 }}>
        {themeEmoji[theme] ?? themeEmoji.Autre}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    alignItems: 'center',
    justifyContent: 'center',
  },
});
