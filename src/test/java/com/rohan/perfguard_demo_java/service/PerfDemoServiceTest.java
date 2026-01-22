package com.rohan.perfguard_demo_java.service;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

class PerfDemoServiceTest {

    @Test
    void uniquePreserveOrder_keepsFirstOccurrenceOrder() {
        PerfDemoService svc = new PerfDemoService();
        List<Integer> out = svc.uniquePreserveOrder(List.of(3, 1, 3, 2, 1));
        assertEquals(List.of(3, 1, 2), out);
    }
}