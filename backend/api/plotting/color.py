
hex2rgb = lambda h : tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
rgb_to_hex = lambda rgb: '#{:02x}{:02x}{:02x}'.format(*(int(c * 255) for c in rgb[:3]))

color_LUT = {
    '#FF0000':'Red',
    '#FFA500':'Orange',
    '#FFFF00':'Yellow',
    '#00FF00':'Green',
    '#0000FF':'Blue',
    '#4B0082':'Indigo',
    '#1E22AA':'JM',
}


# color table to use for picking complimentary colors in graphs https://www.color-hex.com/color/1e22aa
complimentary_LUT = {
    '#FF0000':'#00ffff',
    '#FFA500':'#005aff',
    '#FFFF00':'#0000ff',
    '#00FF00':'#ff00ff',
    '#0000FF':'#ffff00',
    '#4B0082':'#378200',
    '#1E22AA':'#aaa61e',
}

def complimentary_rgba(color):
    """
    find the complementary rgba color given a color from the app dropdown menu

    Args:
        color (string): hex value

    Returns:
        _type_: rgba tuple
    """
    return hex2rgb(complimentary_LUT[color])





















