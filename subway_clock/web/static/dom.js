// What the styles share for building their elements.

// An element with a class and children (elements or text).
export function el(tag, className, ...children) {
    const element = document.createElement(tag)
    if (className)
        element.className = className
    element.append(...children)
    return element
}

// Sizes go to the stylesheet as custom properties in pixels: vars(root, { row: 240 }) sets --row.
export function vars(element, values) {
    for (const [name, value] of Object.entries(values))
        element.style.setProperty("--" + name, value + "px")
}

// An element's text, left alone if it already says so.
export function setText(element, text) {
    text = String(text)
    if (element.textContent !== text)
        element.textContent = text
}

export function bulletUrl(asset) {
    return "assets/bullets/NYCS-bull-trans-" + asset + ".svg"
}

export function bullet(asset, className) {
    const image = el("img", className || "bullet")
    image.alt = ""
    if (asset)
        setBullet(image, asset)
    return image
}

// Change an image's bullet, without loading again the one it has.
export function setBullet(image, asset) {
    if (image.dataset.asset !== asset) {
        image.dataset.asset = asset
        image.src = bulletUrl(asset)
    }
}

// Keep a row of bullets in step with a list of bullet asset ids.
export function setBullets(parent, assets) {
    const key = assets.join(" ")
    if (parent.dataset.assets !== key) {
        parent.dataset.assets = key
        parent.replaceChildren(...assets.map(asset => bullet(asset)))
    }
}

// A service alert as text with its routes' bullets drawn inline ("[4]"), left alone if it already says so.
export function setMessage(element, message) {
    if (element.dataset.message === message)
        return
    element.dataset.message = message
    element.replaceChildren(...Messages.pieces(message).map((piece, i, pieces) => piece.bullet
        ? bullet(piece.bullet, "inline-bullet" + (i > 0 && pieces[i - 1].bullet ? " next" : "")) : piece.text))
}

// Keep `parent`'s children in step with `items`: a part for each, made by make() as
// { element, set(item) }, kept from one time to the next and brought up to date by its set.
export function list(parent, make) {
    const parts = []
    return function (items) {
        while (parts.length > items.length)
            parts.pop().element.remove()
        items.forEach(function (item, i) {
            if (!parts[i]) {
                parts[i] = make()
                parent.append(parts[i].element)
            }
            parts[i].set(item, i)
        })
        return parts
    }
}

// What a start shows where a train's minutes go: how far along loading is, or nothing.
export function percent(startup) {
    return startup.state === "loading" && startup.progress >= 0 ? Math.round(startup.progress * 100) + "%" : ""
}
