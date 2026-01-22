package com.rohan.perfguard_demo_java.service;

import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.List;

@Service
public class PerfDemoService {

    /**
     * Intentionally suboptimal implementation for PerfGuard demo:
     * O(n^2) pattern due to list.contains inside a loop.
     */
    public List<Integer> uniquePreserveOrder(List<Integer> input) {
        List<Integer> result = new ArrayList<>();
        for (Integer x : input) {
            if (!result.contains(x)) { // <-- PerfGuard should flag this later
                result.add(x);
            }
        }
        return result;
    }
}