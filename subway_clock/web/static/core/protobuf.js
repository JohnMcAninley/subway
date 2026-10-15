// Just enough of protobuf's wire format to read the GTFS-realtime feeds: the
// fields the clock uses, by number, and nothing else. The MTA's own fields
// (such as an alert's field 1001) are read the same way as the standard ones,
// as there are no bindings here to not know them.

const VARINT = 0, FIXED64 = 1, BYTES = 2, FIXED32 = 5

// Every field in a message's bytes, as { number, value }: a number for a varint, and for a
// length-delimited field the bytes, which are a string, packed numbers or a message of its own.
export function fields(bytes) {
    const found = []
    let at = 0

    function varint() {
        // Multiplied rather than shifted: times and IDs can be wider than JavaScript's 32-bit bit operations.
        let value = 0, scale = 1, byte
        do {
            if (at >= bytes.length)
                throw new Error("protobuf: truncated varint")
            byte = bytes[at++]
            value += (byte & 0x7f) * scale
            scale *= 128
        } while (byte & 0x80)
        return value
    }

    while (at < bytes.length) {
        const key = varint()
        const number = Math.floor(key / 8), type = key % 8
        let value
        if (type === VARINT) {
            value = varint()
        } else if (type === BYTES) {
            const length = varint()
            if (at + length > bytes.length)
                throw new Error("protobuf: truncated field " + number)
            value = bytes.subarray(at, at + length)
            at += length
        } else if (type === FIXED64 || type === FIXED32) {
            at += type === FIXED64 ? 8 : 4
            continue  // Nothing the clock reads is fixed-width.
        } else {
            throw new Error("protobuf: unknown wire type " + type)
        }
        found.push({ number, value })
    }
    return found
}

const decoder = new TextDecoder()

export function text(bytes) {
    return decoder.decode(bytes)
}

// A message's fields as an object, by `shape`: { name: [number, kind] }, where kind is "int"
// or "string" for the last value given, a shape for the last as an object of that shape, or a
// shape in a list for every value. Absent fields are 0, "", null or [], as in protobuf; "int?"
// is an int that is null when absent, for the few whose presence means something.
export function read(bytes, shape) {
    const message = {}
    const names = {}
    for (const [name, [number, kind]] of Object.entries(shape)) {
        names[number] = name
        message[name] = Array.isArray(kind) ? [] : kind === "int" ? 0 : kind === "string" ? "" : null
    }
    for (const { number, value } of fields(bytes)) {
        const name = names[number]
        if (name === undefined)
            continue
        const kind = shape[name][1]
        if (Array.isArray(kind))
            message[name].push(read(value, kind[0]))
        else if (kind === "int" || kind === "int?")
            message[name] = typeof value === "number" ? value : 0
        else if (kind === "string")
            message[name] = text(value)
        else
            message[name] = read(value, kind)
    }
    return message
}
