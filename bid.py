import sqlite3 as sql

def autobid(auction_listing):
    seller_email = auction_listing[0]
    listing_id = auction_listing[1]

    conn = sql.connect("dataset_tables.db")
    cursor = conn.cursor()

    # Loop handles back-and-forth proxy clashes until the price stabilizes
    while True:

        # Get the current highest bid
        cursor.execute('''
                       SELECT Bidder_email, Bid_price
                       FROM Bids
                       WHERE Listing_ID = ?
                         AND Seller_Email = ?
                       ORDER BY Bid_price DESC, Bid_ID ASC LIMIT 1
                       ''', (listing_id, seller_email))

        current_leader = cursor.fetchone()
        if not current_leader:
            break  # No bids exist for this listing

        leader_email, current_price = current_leader

        # Check if the current leader has an active proxy ceiling
        cursor.execute('''
                       SELECT MAX(a.max_bid), MIN(a.bid_time)
                       FROM Bids b
                                JOIN Auto_Bids a ON b.Bid_ID = a.Bid_ID
                       WHERE b.Listing_ID = ?
                         AND b.Bidder_email = ?
                       ''', (listing_id, leader_email))

        leader_proxy_data = cursor.fetchone()
        leader_max = leader_proxy_data[0] if leader_proxy_data else None
        leader_time = leader_proxy_data[1] if leader_proxy_data else None

        # Find the strongest proxy challenger who is NOT the current leader
        # This prevents users from artificially bidding against themselves
        cursor.execute('''
                       SELECT b.Bidder_email, MAX(a.max_bid) as highest_max, MIN(a.bid_time) as first_bid_time
                       FROM Bids b
                                JOIN Auto_Bids a ON b.Bid_ID = a.Bid_ID
                       WHERE b.Listing_ID = ?
                         AND b.Seller_Email = ?
                         AND b.Bidder_email != ?
                       GROUP BY b.Bidder_email
                       ORDER BY highest_max DESC, first_bid_time ASC
                           LIMIT 1
                       ''', (listing_id, seller_email, leader_email))

        challenger = cursor.fetchone()

        if not challenger:
            break  # No opponent exists to push the price up

        challenger_email, challenger_max, challenger_time = challenger

        # Enforce the strict $1 minimum increment constraint
        if challenger_max < current_price + 1:
            break  # Challenger's ceiling is too low to legally outbid the leader

        # Resolve the clash
        new_bid_price = current_price + 1
        winner_email = challenger_email
        winner_time = challenger_time
        winner_max = challenger_max

        # If both users have active proxies, calculate the final jump instantly
        if leader_max and leader_max >= current_price + 1:
            if challenger_max > leader_max:
                # Challenger beats leader's absolute max
                new_bid_price = leader_max + 1
            elif leader_max > challenger_max:
                # Leader beats challenger's absolute max
                new_bid_price = challenger_max + 1
                winner_email = leader_email
                winner_time = leader_time
                winner_max = leader_max
            else:
                # Absolute Tie: The earlier bid wins
                if leader_time <= challenger_time:
                    new_bid_price = challenger_max  # Price caps out
                    winner_email = leader_email
                    winner_time = leader_time
                    winner_max = leader_max
                else:
                    new_bid_price = leader_max

        # Safety: Ensure the calculation never exceeds the winner's absolute maximum
        if new_bid_price > winner_max:
            new_bid_price = winner_max

        # Insert the newly calculated winning bid
        cursor.execute('''
                       INSERT INTO Bids (Seller_Email, Listing_ID, Bidder_email, Bid_price)
                       VALUES (?, ?, ?, ?)
                       ''', (seller_email, listing_id, winner_email, new_bid_price))

        new_bid_id = cursor.lastrowid #

        # Carry the winner's proxy ceiling forward so it remains active
        cursor.execute('''
                       INSERT INTO Auto_Bids (Bid_ID, max_bid, bid_time)
                       VALUES (?, ?, ?)
                       ''', (new_bid_id, winner_max, winner_time))
        conn.commit()

        # The loop will restart and verify no other proxy challengers exist
    conn.close()
