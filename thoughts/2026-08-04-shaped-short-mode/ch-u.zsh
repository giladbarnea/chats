#!/usr/bin/env -S FORCE_OMZ=1 zsh -i
set -euo pipefail

(( $# == 1 )) || {
    print -u2 "Usage: ${0:t} SESSION_ID"
    exit 64
}

session_id=$1
message_count=$(ch "$session_id" -l | yq '.messages')
[[ "$message_count" == <-> ]] || {
    print -u2 "Could not get a numeric message count for session $session_id."
    exit 1
}
(( message_count >= 2 )) || {
    print -u2 "The U curve needs at least two messages."
    exit 1
}

size_weight=1
curve_steepness=4
minimum_short_length=8

typeset -a message_sizes
maximum_size=0

for (( message_index = 1; message_index <= message_count; message_index++ )); do
    message_size=$(ch "$session_id" "$message_index" --no-metadata | wc -c)
    message_sizes[$message_index]=$message_size
    maximum_size=$(( message_size > maximum_size ? message_size : maximum_size ))
done

for (( message_index = 1; message_index <= message_count; message_index++ )); do
    short_limit=$(
        awk \
            -v message_index="$message_index" \
            -v message_count="$message_count" \
            -v message_size="${message_sizes[$message_index]}" \
            -v maximum_size="$maximum_size" \
            -v size_weight="$size_weight" \
            -v curve_steepness="$curve_steepness" \
            'BEGIN {
                position = (message_index - 1) / (message_count - 1)
                center_distance = 2 * position - 1
                center_distance = center_distance < 0 ? -center_distance : center_distance
                position_factor = center_distance ^ curve_steepness
                size_factor = maximum_size ^ (1 - size_weight) * message_size ^ size_weight
                printf "%.0f", position_factor * size_factor
            }'
    )

    ch \
        "$session_id" \
        "$message_index" \
        --no-metadata \
        --short="$(( short_limit < minimum_short_length ? minimum_short_length : short_limit ))"
done
